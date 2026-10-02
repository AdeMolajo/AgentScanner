"""Core scanning functionality for AgentScanner."""

from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import asyncio
from playwright.async_api import async_playwright


class ScanResult(BaseModel):
    """Represents the result of an agent scan."""
    agent_path: str
    issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    info: Dict[str, Any] = {}


class AgentScanner:
    """Main scanner class for analyzing agents."""

    def __init__(self, provider: Optional[str] = None):
        """Initialize the scanner.

        Args:
            provider: Optional LLM provider for semantic analysis (e.g., 'openai')
        """
        self.provider = provider
        self.results: List[ScanResult] = []

    def scan(self, path: str) -> ScanResult:
        """Scan an agent or skill directory.

        Args:
            path: Path to scan (local dir, file, URL, or zip)

        Returns:
            ScanResult with findings
        """
        result = ScanResult(agent_path=path)

        # Check if it's a URL
        if path.startswith(("http://", "https://")):
            return self._scan_url(path, result)

        # Handle local paths
        target_path = Path(path)
        return self._scan_local(target_path, result)

    def _scan_url(self, url: str, result: ScanResult) -> ScanResult:
        """Scan a remote URL (webpage, Notion, etc)."""
        # Check if URL requires JavaScript rendering (Notion, etc)
        if "notion.site" in url or "notion.so" in url:
            return self._scan_url_with_js(url, result)

        # Otherwise use static HTML fetching
        return self._scan_url_static(url, result)

    def _scan_url_static(self, url: str, result: ScanResult) -> ScanResult:
        """Scan a URL with static HTML parsing."""
        try:
            headers = {
                "User-Agent": "AgentScanner/0.1.0 (https://github.com/AdeMolajo/AgentScanner)"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse HTML content
            soup = BeautifulSoup(response.content, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)

            # Store metadata
            result.info = {
                "url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "content_length": len(text_content),
                "lines": len(text_content.split("\n")),
                "title": soup.title.string if soup.title else "No title",
                "render_method": "static",
            }

            self._analyze_content(text_content, result)

        except requests.exceptions.RequestException as e:
            result.issues.append({
                "type": "fetch_error",
                "message": f"Failed to fetch URL: {str(e)}",
                "severity": "error"
            })

        self.results.append(result)
        return result

    def _scan_url_with_js(self, url: str, result: ScanResult) -> ScanResult:
        """Scan a URL with JavaScript rendering using Playwright."""
        try:
            text_content = asyncio.run(self._fetch_with_playwright(url))

            # Check if we got meaningful content or hit Cloudflare
            is_cloudflare_challenge = (
                "Just a moment" in text_content or
                "Enable JavaScript and cookies" in text_content or
                "Cloudflare" in text_content
            )

            # Store metadata
            result.info = {
                "url": url,
                "status_code": 200,
                "content_type": "text/html",
                "content_length": len(text_content),
                "lines": len(text_content.split("\n")),
                "render_method": "javascript",
                "note": "Rendered with Playwright",
            }

            if is_cloudflare_challenge:
                result.warnings.append({
                    "type": "cloudflare_protection",
                    "message": "Page is protected by Cloudflare - content may be incomplete",
                    "severity": "warning"
                })

            self._analyze_content(text_content, result)

        except Exception as e:
            result.issues.append({
                "type": "render_error",
                "message": f"Failed to render URL with JavaScript: {str(e)}",
                "severity": "error"
            })

        self.results.append(result)
        return result

    async def _fetch_with_playwright(self, url: str) -> str:
        """Fetch and render a URL using Playwright."""
        async with async_playwright() as p:
            # Launch with more realistic browser settings to bypass bot detection
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            page = await browser.new_page(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                # Wait for dynamic content and bot challenges
                await page.wait_for_timeout(5000)

                # Try to get content from multiple sources
                text_content = await page.evaluate("""
                    () => {
                        // Try various methods to get content
                        let content = '';

                        // Try body innerText
                        if (document.body.innerText) {
                            content = document.body.innerText;
                        }

                        // If minimal content, try documentElement
                        if (!content || content.length < 100) {
                            content = document.documentElement.textContent || '';
                        }

                        // Remove excessive whitespace
                        content = content.replace(/\\s+/g, ' ').trim();

                        return content;
                    }
                """)

                return text_content
            finally:
                await browser.close()

    def _scan_local(self, path: Path, result: ScanResult) -> ScanResult:
        """Scan a local file or directory."""
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="ignore")
            result.info = {
                "path": str(path),
                "type": "file",
                "size": path.stat().st_size,
                "extension": path.suffix,
            }
            self._analyze_content(content, result)

        elif path.is_dir():
            result.info = {
                "path": str(path),
                "type": "directory",
                "files": len(list(path.glob("**/*"))),
            }
            for file_path in path.glob("**/*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        self._analyze_content(content, result)
                    except Exception:
                        pass

        self.results.append(result)
        return result

    def _analyze_content(self, content: str, result: ScanResult) -> None:
        """Perform static analysis on content."""
        import re
        suspicious_patterns = [
            ("sql_injection", r"SELECT\s+.*\s+FROM", "Potential SQL injection pattern"),
            ("hardcoded_secret", r"(api_key|password|secret|token)\s*[=:]\s*['\"]", "Potential hardcoded secret"),
            ("eval_usage", r"\beval\s*\(", "Use of eval() detected"),
        ]

        for pattern_name, pattern, message in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result.warnings.append({
                    "type": pattern_name,
                    "message": message,
                    "severity": "warning"
                })

    def get_results(self, format: str = "terminal") -> str:
        """Get formatted scan results.

        Args:
            format: Output format ('terminal', 'json', 'markdown', 'sarif')

        Returns:
            Formatted results string
        """
        if format == "json":
            return self._format_json()
        elif format == "markdown":
            return self._format_markdown()
        elif format == "sarif":
            return self._format_sarif()
        else:
            return self._format_terminal()

    def _format_terminal(self) -> str:
        """Format results for terminal output."""
        # TODO: Implement pretty terminal formatting
        return str(self.results)

    def _format_json(self) -> str:
        """Format results as JSON."""
        import json
        return json.dumps([r.model_dump() for r in self.results], indent=2)

    def _format_markdown(self) -> str:
        """Format results as Markdown."""
        # TODO: Implement markdown formatting
        return "\n".join([f"## {r.agent_path}" for r in self.results])

    def _format_sarif(self) -> str:
        """Format results as SARIF."""
        # TODO: Implement SARIF formatting
        return "{}"
