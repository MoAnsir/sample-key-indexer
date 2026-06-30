import { useState, useEffect, useCallback } from "react";
import { browseFolders, type FolderEntry } from "../api/client";

interface FolderBrowserProps {
  value: string;
  onChange: (path: string) => void;
  placeholder?: string;
}

export default function FolderBrowser({ value, onChange, placeholder }: FolderBrowserProps) {
  const [open, setOpen] = useState(false);
  const [currentPath, setCurrentPath] = useState("");
  const [folders, setFolders] = useState<FolderEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [roots, setRoots] = useState<FolderEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const navigate = useCallback(async (path?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await browseFolders(path);
      if (data.error) {
        setError(data.error);
        return;
      }
      setCurrentPath(data.path);
      setFolders(data.folders);
      if (!path) setRoots(data.folders);
    } catch (err) {
      setError("Failed to browse folders. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      if (value && value.startsWith("/")) {
        navigate(value);
      } else {
        navigate();
      }
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectFolder = useCallback((path: string) => {
    onChange(path);
    setOpen(false);
  }, [onChange]);

  const pathParts = currentPath ? currentPath.split("/").filter(Boolean) : [];

  return (
    <div className="space-y-2">
      {/* Text input + browse button */}
      <div className="flex gap-2">
        <input
          type="text"
          className="input-base flex-1"
          placeholder={placeholder ?? "/path/to/folder"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="px-3 py-1.5 text-xs font-medium rounded-control border border-line bg-surface-2 text-ink hover:bg-surface transition-colors whitespace-nowrap"
        >
          {open ? "Close" : "Browse..."}
        </button>
      </div>

      {/* Folder browser panel */}
      {open && (
        <div className="border border-line rounded-panel bg-surface shadow-pop overflow-hidden" style={{ height: 340 }}>
          <div className="flex h-full">
            {/* Sidebar — quick access */}
            <div className="w-36 border-r border-line bg-surface-2 py-2 shrink-0 overflow-y-auto">
              <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-faint">Quick Access</p>
              {roots.map((r) => (
                <button
                  key={r.path}
                  onClick={() => navigate(r.path)}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-surface transition-colors ${
                    currentPath === r.path ? "bg-surface text-ink font-medium" : "text-muted"
                  }`}
                >
                  <span>📁</span>
                  <span className="truncate">{r.name}</span>
                </button>
              ))}
            </div>

            {/* Main area */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Breadcrumb navigation */}
              <div className="flex items-center gap-1 px-3 py-2 border-b border-line bg-surface-2 shrink-0 overflow-x-auto">
                <button
                  onClick={() => navigate()}
                  className="text-xs text-accent hover:underline shrink-0"
                >
                  Locations
                </button>
                {pathParts.map((part, i) => {
                  const fullPath = "/" + pathParts.slice(0, i + 1).join("/");
                  return (
                    <span key={fullPath} className="flex items-center gap-1 shrink-0">
                      <span className="text-faint text-xs">/</span>
                      <button
                        onClick={() => navigate(fullPath)}
                        className="text-xs text-accent hover:underline"
                      >
                        {part}
                      </button>
                    </span>
                  );
                })}
              </div>

              {/* Select current folder bar */}
              {currentPath && (
                <div className="flex items-center justify-between px-3 py-1.5 border-b border-line bg-accent-soft shrink-0">
                  <span className="text-xs font-mono text-ink truncate">{currentPath}</span>
                  <button
                    onClick={() => selectFolder(currentPath)}
                    className="px-3 py-1 text-xs font-medium rounded-control bg-accent text-white hover:opacity-90 transition-opacity shrink-0 ml-2"
                  >
                    Select this folder
                  </button>
                </div>
              )}

              {/* Folder list */}
              <div className="flex-1 overflow-y-auto">
                {loading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
                  </div>
                ) : error ? (
                  <div className="p-4 text-center text-xs text-warn">{error}</div>
                ) : folders.length === 0 ? (
                  <div className="p-4 text-center text-xs text-faint">
                    No subfolders in this directory
                  </div>
                ) : (
                  <div className="py-1">
                    {folders.map((folder) => (
                      <button
                        key={folder.path}
                        onClick={() => navigate(folder.path)}
                        onDoubleClick={() => selectFolder(folder.path)}
                        className="w-full flex items-center gap-2.5 px-3 py-1.5 text-left hover:bg-surface-2 transition-colors group"
                      >
                        <span className="text-base shrink-0">📁</span>
                        <span className="text-sm text-ink truncate flex-1">{folder.name}</span>
                        <span className="text-[10px] text-faint opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                          double-click to select
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
