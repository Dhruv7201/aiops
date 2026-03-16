"""Frontend project generator using React + Vite."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aiops.core.log import get_logger

logger = get_logger(__name__)


class FrontendGenerator:
    """Generate a React + Vite frontend project with dashboard layout.

    Usage:
        gen = FrontendGenerator()
        gen.generate("my_dashboard", api_url="http://localhost:8000")
    """

    def generate(
        self,
        project_name: str,
        output_dir: str | Path = ".",
        *,
        api_url: str = "http://localhost:8000",
        template: str = "react-ts",
    ) -> Path:
        root = Path(output_dir) / project_name

        # Scaffold with Vite (non-interactive, with timeout)
        scaffolded = False
        try:
            result = subprocess.run(
                ["npm", "create", "vite@latest", project_name, "--", "--template", template],
                cwd=str(Path(output_dir)),
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
            scaffolded = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        if not scaffolded:
            logger.info("Vite CLI unavailable or failed — using built-in scaffold")
            root.mkdir(parents=True, exist_ok=True)
            self._manual_scaffold(root, project_name, template)

        # Add custom files
        self._gen_env(root, api_url)
        self._gen_api_client(root, api_url)
        self._gen_dashboard_layout(root)

        logger.info(f"Generated React+Vite project at {root}")
        return root

    @staticmethod
    def _gen_env(root: Path, api_url: str) -> None:
        (root / ".env").write_text(f"VITE_API_URL={api_url}\n")
        (root / ".env.example").write_text("VITE_API_URL=http://localhost:8000\n")

    @staticmethod
    def _gen_api_client(root: Path, api_url: str) -> None:
        src = root / "src"
        src.mkdir(exist_ok=True)
        lib_dir = src / "lib"
        lib_dir.mkdir(exist_ok=True)

        (lib_dir / "api.ts").write_text('''const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...init } = options;

  let url = `${API_URL}${endpoint}`;
  if (params) {
    url += "?" + new URLSearchParams(params).toString();
  }

  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, string>) =>
    request<T>(endpoint, { params }),

  post: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: "POST", body: JSON.stringify(body) }),

  put: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: "PUT", body: JSON.stringify(body) }),

  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: "DELETE" }),
};
''')

    @staticmethod
    def _gen_dashboard_layout(root: Path) -> None:
        components = root / "src" / "components"
        components.mkdir(parents=True, exist_ok=True)

        (components / "Layout.tsx").write_text('''import { ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <main style={{ flex: 1, padding: "24px" }}>
        <Header />
        {children}
      </main>
    </div>
  );
}

function Sidebar() {
  return (
    <aside style={{
      width: "240px",
      background: "#1a1a2e",
      color: "white",
      padding: "20px",
    }}>
      <h2 style={{ marginBottom: "32px" }}>Dashboard</h2>
      <nav>
        <ul style={{ listStyle: "none", padding: 0 }}>
          <li style={{ marginBottom: "12px" }}><a href="/" style={{ color: "#e0e0e0" }}>Home</a></li>
          <li style={{ marginBottom: "12px" }}><a href="/analytics" style={{ color: "#e0e0e0" }}>Analytics</a></li>
          <li style={{ marginBottom: "12px" }}><a href="/settings" style={{ color: "#e0e0e0" }}>Settings</a></li>
        </ul>
      </nav>
    </aside>
  );
}

function Header() {
  return (
    <header style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: "24px",
      paddingBottom: "16px",
      borderBottom: "1px solid #e0e0e0",
    }}>
      <h1>Dashboard</h1>
    </header>
  );
}
''')

    @staticmethod
    def _manual_scaffold(root: Path, name: str, template: str) -> None:
        """Fallback scaffold if npm/vite not available."""
        src = root / "src"
        src.mkdir(parents=True, exist_ok=True)

        (root / "package.json").write_text(f'''{{
  "name": "{name}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  }},
  "devDependencies": {{
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }}
}}
''')

        (root / "index.html").write_text(f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''')

        (src / "main.tsx").write_text('''import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
''')

        (src / "App.tsx").write_text('''import { Layout } from "./components/Layout";

export default function App() {
  return (
    <Layout>
      <h2>Welcome to your dashboard</h2>
    </Layout>
  );
}
''')
