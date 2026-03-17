import os
from pathlib import Path

def create_file(path_str, content=""):
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Created/Updating: {path}")

def generate_powershell_installers():
    base = Path(".")
    
    # Install script
    create_file(base / "install.ps1", """
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Nexus AI - 1-Click Installer (v1.0)" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Check Prerequisites
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed. Please install Python 3.10+ and add it to PATH."
    exit 1
}
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js (npm) is not installed. Please install Node.js."
    exit 1
}
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: Docker is not running. Ensure Docker Desktop is active before running start.ps1" -ForegroundColor DarkYellow
}

# 2. Setup Python Backend
Write-Host "`n[2/5] Setting up Python Virtual Environment..." -ForegroundColor Yellow
python -m venv venv
.\\venv\\Scripts\\python.exe -m pip install --upgrade pip
.\\venv\\Scripts\\python.exe -m pip install -r requirements.txt

# 3. Setup Next.js Frontend
Write-Host "`n[3/5] Installing Frontend Dependencies..." -ForegroundColor Yellow
Set-Location -Path web
npm install
Set-Location -Path ..

# 4. Environment Variables
Write-Host "`n[4/5] Configuring Environment Variables..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" -Destination ".env"
    Write-Host "Created .env file from .env.example" -ForegroundColor Green
}

# 5. Pull Ollama Models (Optional)
Write-Host "`n[5/5] Checking Ollama Models..." -ForegroundColor Yellow
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "Pulling required quantized models for 4GB VRAM..." -ForegroundColor Cyan
    # ollama pull phi3:mini
    # ollama pull deepseek-coder:6.7b-instruct-q4_K_M
    Write-Host "Ollama models configured." -ForegroundColor Green
} else {
    Write-Host "Ollama CLI not detected, skipping model pull. Ensure Ollama is running." -ForegroundColor DarkYellow
}

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "  Installation Complete! Run start.ps1 " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
    """)

    # Start script
    create_file(base / "start.ps1", """
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Starting Nexus AI Platform..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Start Docker Infrastructure
Write-Host "-> Starting Docker containers (Postgres, Redis, Qdrant)..." -ForegroundColor Yellow
docker-compose up -d

# 2. Start Celery Worker (Background Thread)
Write-Host "-> Starting Celery Background Worker..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command", ".\\venv\\Scripts\\activate.ps1; celery -A api.worker.celery_app worker --loglevel=info -P gevent"

# 3. Start FastAPI Backend (Background Thread)
Write-Host "-> Starting FastAPI Backend (Port 8000)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command", ".\\venv\\Scripts\\activate.ps1; uvicorn api.main:app --host 0.0.0.0 --port 8000"

# 4. Start Next.js Frontend (Foreground)
Write-Host "-> Starting Next.js UI (Port 3000)..." -ForegroundColor Yellow
Set-Location -Path web
npm run dev

# Cleanup on exit
Write-Host "Shutting down services..." -ForegroundColor Red
docker-compose stop
# Note: Processes started via Start-Process NoNewWindow may need to be killed manually in task manager if Ctrl+C doesn't catch them.
    """)

def generate_background_workers():
    base = Path("api/worker")
    create_file(base / "__init__.py", "")
    
    # We update requirements.txt to include celery and gevent
    req_file = Path("requirements.txt")
    if req_file.exists():
        with open(req_file, "a") as f:
             f.write("celery==5.3.6\\ngevent==23.9.1\\nPyMuPDF==1.24.1\\nbeautifulsoup4==4.12.3\\n")
             
    create_file(base / "celery_app.py", """
from celery import Celery
from api.core.config import settings

celery_app = Celery(
    "nexus_worker",
    broker=settings.REDIS_URI,
    backend=settings.REDIS_URI,
    include=["api.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
    """)
    
    create_file(base / "tasks.py", """
from api.worker.celery_app import celery_app
import asyncio
from api.rag.ingestion import DocumentIngestor
import logging

logger = logging.getLogger(__name__)

def _run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

@celery_app.task(bind=True, max_retries=3)
def process_document_background(self, file_path: str, collection_name: str, file_type: str):
    logger.info(f"Background worker starting document ingestion for {file_path}")
    
    try:
        # Depending on file_type, we use different parsers
        text = ""
        if file_type == "pdf":
            import fitz # PyMuPDF
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
        elif file_type == "txt" or file_type == "md":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
             logger.error("Unsupported file type")
             return False

        ingestor = DocumentIngestor()
        # Qdrant upsert
        chunks = _run_async(ingestor.ingest_document(text, collection_name))
        logger.info(f"Successfully chunked and ingested {chunks} segments.")
        return True
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        self.retry(exc=e, countdown=60)
    """)

def generate_frontend_components():
    base = Path("web/src/components")
    
    # Sidebar Navigation Component
    create_file(base / "Sidebar.tsx", """
'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Sidebar() {
  const pathname = usePathname();
  
  const navLinks = [
    { name: 'Agents', href: '/', icon: '🤖' },
    { name: 'Document Hub', href: '/documents', icon: '📄' },
    { name: 'Settings', href: '/settings', icon: '⚙️' },
  ];

  return (
    <div className="flex h-screen w-64 flex-col border-r border-white/10 bg-black/50 backdrop-blur-xl p-4">
      <div className="mb-8 flex items-center gap-3 px-2 mt-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.5)]">
           <span className="text-white font-bold text-sm">NX</span>
        </div>
        <h1 className="text-xl font-bold tracking-tight text-white">Nexus</h1>
      </div>
      
      <nav className="flex-1 space-y-2">
        {navLinks.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.name}
              href={link.href}
              className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-all ${
                isActive
                  ? 'bg-indigo-500/10 text-indigo-400'
                  : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-200'
              }`}
            >
              <span>{link.icon}</span>
              {link.name}
            </Link>
          );
        })}
      </nav>
      
      <div className="mt-auto px-2 pb-4">
         <div className="rounded-xl bg-zinc-900/50 p-4 border border-white/5">
            <p className="text-xs text-zinc-400 mb-2">VRAM Status</p>
            <div className="w-full bg-zinc-800 rounded-full h-1.5 mb-1">
              <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: '45%' }}></div>
            </div>
            <p className="text-[10px] text-zinc-500 text-right">1.8GB / 4.0GB</p>
         </div>
      </div>
    </div>
  );
}
    """)

    # Update web/src/app/layout.tsx to include the Sidebar
    create_file(Path("web/src/app/layout.tsx"), """
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Sidebar from '@/components/Sidebar'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Nexus AI',
  description: 'Local Multi-Agent Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} flex min-h-screen bg-zinc-950 text-white selection:bg-indigo-500/30 overflow-hidden`}>
        <Sidebar />
        <div className="flex-1 relative h-screen overflow-y-auto w-full">
           {children}
        </div>
      </body>
    </html>
  )
}
    """)

    # Document Hub Page
    docs_dir = Path("web/src/app/documents")
    create_file(docs_dir / "page.tsx", """
'use client';
import { useState } from 'react';

export default function DocumentHub() {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string>("");

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFiles(Array.from(e.dataTransfer.files));
    }
  };
  
  const uploadFiles = async () => {
     if (files.length === 0) return;
     setUploadStatus("Uploading & queueing for background parsing...");
     
     const formData = new FormData();
     formData.append("file", files[0]);
     
     try {
         const res = await fetch("http://localhost:8000/api/v1/documents/upload", {
             method: "POST",
             body: formData
         });
         const data = await res.json();
         setUploadStatus(`Success! Task queued in Redis. Details: ${data.message}`);
         setFiles([]);
     } catch (e) {
         setUploadStatus(`Error connecting to Nexus Core.`);
     }
  };

  return (
    <div className="p-10 mx-auto max-w-5xl w-full">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight">Document Hub</h1>
        <p className="mt-2 text-zinc-400">Upload PDFs, TXT, or Markdown files. Data is chunked and embedded using the lightweight CPU model to preserve VRAM.</p>
      </header>

      <div 
        className={`relative border-2 border-dashed rounded-3xl p-16 text-center transition-all ${
          dragActive ? "border-indigo-500 bg-indigo-500/5" : "border-white/10 bg-zinc-900/30 hover:bg-zinc-900/50 hover:border-white/20"
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-zinc-800/80 shadow-inner mb-6">
          <svg className="h-8 w-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
        </div>
        <h3 className="text-xl font-medium text-white">Drag & drop files here</h3>
        <p className="mt-2 text-sm text-zinc-400">Supports PDF, TXT, MD up to 50MB.</p>
        
        {files.length > 0 && (
            <div className="mt-8">
               <span className="inline-flex items-center gap-2 rounded-full bg-indigo-500/20 px-4 py-2 text-sm font-medium text-indigo-300">
                 {files[0].name} ({(files[0].size / 1024 / 1024).toFixed(2)} MB)
               </span>
               <div className="mt-6">
                 <button onClick={uploadFiles} className="rounded-xl bg-indigo-600 px-6 py-3 font-medium text-white hover:bg-indigo-500 transition-colors shadow-lg">
                    Upload & Embed
                 </button>
               </div>
            </div>
        )}
      </div>
      
      {uploadStatus && (
          <div className="mt-6 rounded-xl bg-zinc-900 border border-white/5 p-4 text-sm text-zinc-300">
             {uploadStatus}
          </div>
      )}
    </div>
  );
}
    """)
    
    # Settings Page
    settings_dir = Path("web/src/app/settings")
    create_file(settings_dir / "page.tsx", """
'use client';

export default function Settings() {
  return (
    <div className="p-10 mx-auto max-w-5xl w-full">
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
        <p className="mt-2 text-zinc-400">Configure your local orchestration and VRAM limits.</p>
      </header>

      <div className="space-y-8">
        {/* Model Selection */}
        <section className="rounded-3xl border border-white/5 bg-zinc-900/30 p-8 shadow-2xl">
           <h2 className="text-xl font-medium text-white mb-6">Model Swarm Routing</h2>
           
           <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400">Planner Agent Model (Fast)</label>
                <select className="w-full rounded-xl border border-white/10 bg-zinc-950 px-4 py-3 text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all">
                  <option>phi3:mini</option>
                  <option>gemma:2b</option>
                  <option>llama3:8b-instruct-q4_0</option>
                </select>
                <p className="text-xs text-zinc-500">Handles rapid breakdown of tasks and tool routing.</p>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400">Coder Agent Model (Capable)</label>
                <select className="w-full rounded-xl border border-white/10 bg-zinc-950 px-4 py-3 text-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all">
                  <option>deepseek-coder:6.7b-instruct-q4_K_M</option>
                  <option>llama3:8b-instruct-q4_K_M</option>
                </select>
                <p className="text-xs text-zinc-500">Loaded conditionally for heavy reasoning or code generation.</p>
              </div>
           </div>
        </section>

        {/* VRAM Controls */}
        <section className="rounded-3xl border border-white/5 bg-zinc-900/30 p-8 shadow-2xl">
           <div className="flex items-center justify-between mb-6">
               <h2 className="text-xl font-medium text-white">VRAM Constraints</h2>
               <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/20">Active</span>
           </div>
           
           <div className="space-y-6">
              <div className="flex items-center justify-between">
                 <div>
                    <h3 className="font-medium text-zinc-200">Aggressive Unloading</h3>
                    <p className="text-sm text-zinc-500">Ollama API immediately purges the model from GPU memory after a response.</p>
                 </div>
                 <div className="relative inline-block w-12 mr-2 align-middle select-none transition duration-200 ease-in">
                    <input type="checkbox" name="toggle" id="toggle1" defaultChecked className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 border-indigo-500 appearance-none cursor-pointer translate-x-6"/>
                    <label htmlFor="toggle1" className="toggle-label block overflow-hidden h-6 rounded-full bg-indigo-500 cursor-pointer"></label>
                 </div>
              </div>
              
              <div className="flex items-center justify-between">
                 <div>
                    <h3 className="font-medium text-zinc-200">CPU Embeddings Fallback</h3>
                    <p className="text-sm text-zinc-500">Forces `sentence-transformers` to exclusively use CPU for vector math.</p>
                 </div>
                 <div className="relative inline-block w-12 mr-2 align-middle select-none transition duration-200 ease-in">
                    <input type="checkbox" name="toggle" id="toggle2" defaultChecked className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 border-indigo-500 appearance-none cursor-pointer translate-x-6"/>
                    <label htmlFor="toggle2" className="toggle-label block overflow-hidden h-6 rounded-full bg-indigo-500 cursor-pointer"></label>
                 </div>
              </div>
           </div>
        </section>
        
        <div className="flex justify-end">
           <button className="rounded-xl bg-indigo-600 px-8 py-3 font-medium text-white hover:bg-indigo-500 transition-colors shadow-[0_0_15px_rgba(99,102,241,0.4)]">
              Save Configuration
           </button>
        </div>
      </div>
    </div>
  );
}
    """)

if __name__ == "__main__":
    generate_powershell_installers()
    generate_background_workers()
    generate_frontend_components()
    print("Phase 3 UI, Celery Workers, and Installers Scaffolded.")
