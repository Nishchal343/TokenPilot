import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Code2,
  FileCode2,
  FilePlus2,
  FolderOpen,
  FolderPlus,
  PanelBottom,
  PanelRight,
  Search,
  Terminal,
  X,
} from "lucide-react";
import { workspaceManager } from "../services/workspaceManager";
import AIChat from "./AIChat";
import "./AIIDE.css";

const MonacoEditor = lazy(() => import("@monaco-editor/react"));
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const languageFor = (name) =>
  ({
    js: "javascript",
    jsx: "javascript",
    ts: "typescript",
    tsx: "typescript",
    py: "python",
    json: "json",
    css: "css",
    html: "html",
    md: "markdown",
    sql: "sql",
  })[name.split(".").pop()?.toLowerCase()] || "plaintext";
const normalize = (nodes) =>
  (nodes || []).map((node) => ({
    ...node,
    id: node.id || node.path || node.name,
    isDirectory: node.isDirectory ?? node.kind === "directory",
    children: normalize(node.children || []),
  }));
const childrenOf = (result) =>
  Array.isArray(result) ? result : result?.children || [];
const codeBlocks = (content) =>
  [...String(content || "").matchAll(/```([\w-]*)\s*\n?([\s\S]*?)```/g)]
    .map((match) => ({
      language: (
        match[1] ||
        (match[2].trimStart().startsWith("<!DOCTYPE html") ||
        match[2].trimStart().startsWith("<html")
          ? "html"
          : "")
      ).toLowerCase(),
      content: match[2].trimEnd(),
    }))
    .filter((block) => block.content.trim());
const extensionFor = (language) =>
  ({
    html: "html",
    htm: "html",
    css: "css",
    javascript: "js",
    js: "js",
    jsx: "jsx",
    typescript: "ts",
    ts: "ts",
    json: "json",
    python: "py",
    py: "py",
    sql: "sql",
    markdown: "md",
    md: "md",
  })[language] || "txt";
const fileNameFromPrompt = (prompt, language) => {
  const match = String(prompt || "").match(
    /(?:file|named|called)\s+["'`]?([\w.-]+\.[\w-]+)["'`]?/i,
  );
  if (match) return match[1];
  const ext = extensionFor(language);
  return ext === "html" ? "index.html" : `generated.${ext}`;
};

function Tree({ nodes, depth = 0, expanded, toggle, open, filter }) {
  return nodes.map((node) => {
    const match =
      !filter || node.name.toLowerCase().includes(filter.toLowerCase());
    if (node.isDirectory) {
      const isOpen = expanded.has(node.id);
      return (
        <div key={node.id} className="ide-tree-branch">
          <button
            className="ide-tree-node folder"
            style={{ paddingLeft: 12 + depth * 16 }}
            onClick={() => toggle(node)}
          >
            <ChevronRight className={isOpen ? "expanded" : ""} size={14} />
            <span>{isOpen ? "📂" : "📁"}</span>
            <b>{node.name}</b>
          </button>
          {isOpen && (
            <Tree
              nodes={node.children}
              depth={depth + 1}
              expanded={expanded}
              toggle={toggle}
              open={open}
              filter={filter}
            />
          )}
        </div>
      );
    }
    return (
      match && (
        <button
          key={node.id}
          className="ide-tree-node file"
          style={{ paddingLeft: 32 + depth * 16 }}
          onClick={() => open(node)}
        >
          <FileCode2 size={14} />
          <span>{node.name}</span>
        </button>
      )
    );
  });
}

export default function AIIDE() {
  const saved = (key) => Number(localStorage.getItem(key));
  const [workspace, setWorkspace] = useState(null);
  const [tree, setTree] = useState([]);
  const [expanded, setExpanded] = useState(new Set());
  const [query, setQuery] = useState("");
  const [tabs, setTabs] = useState([]);
  const [activeId, setActiveId] = useState();
  const [left, setLeft] = useState(() => saved("ide-left-width") || 240);
  const [right, setRight] = useState(() => saved("ide-right-width") || 340);
  const [bottomHeight, setBottomHeight] = useState(
    () => saved("ide-bottom-height") || 220,
  );
  const [leftClosed, setLeftClosed] = useState(
    () => localStorage.getItem("ide-left-closed") === "1",
  );
  const [rightClosed, setRightClosed] = useState(
    () => localStorage.getItem("ide-right-closed") === "1",
  );
  const [bottomOpen, setBottomOpen] = useState(true);
  const [bottom, setBottom] = useState("terminal");
  const [drag, setDrag] = useState(null);
  const [output, setOutput] = useState([
    "Open a folder to start a workspace terminal.",
  ]);
  const rootRef = useRef();
  const editorRef = useRef();
  const saveTimer = useRef();
  const active = tabs.find((tab) => tab.id === activeId);
  const [terminalSession, setTerminalSession] = useState(null);
  const activateWorkspace = async (result, restored = false) => {
    if (!result) return;
    const nodes = normalize(childrenOf(result));
    const terminal = await window.tokenpilotDesktop?.terminal.create();
    const session = terminal?.ok
      ? terminal
      : {
          ok: true,
          sessionId: `browser-${Date.now()}`,
          workspacePath: workspaceManager.root?.name || "Workspace",
          currentWorkingDirectory: "",
        };
    setWorkspace({
      name: workspaceManager.root?.name || "Workspace",
      path: workspaceManager.root?.path,
    });
    setTree(nodes);
    setExpanded(
      new Set(nodes.filter((node) => node.isDirectory).map((node) => node.id)),
    );
    setTabs([]);
    setActiveId();
    setTerminalSession(session);
    setOutput((lines) => [
      ...lines,
      `${restored ? "Restored" : "Opened"} ${workspaceManager.root?.name || "workspace"}`,
      `${session.workspacePath}${session.currentWorkingDirectory ? `/${session.currentWorkingDirectory}` : ""}>`,
    ]);
  };
  useEffect(() => {
    workspaceManager.restore().then((result) => activateWorkspace(result, true)).catch(() => {});
  }, []);
  const browserTerminal = async (command) => {
    const [verb, ...parts] = command.trim().split(/\s+/);
    const name = verb?.toLowerCase();
    const current = terminalSession?.currentWorkingDirectory || "";
    if (name === "clear" || name === "cls")
      return { clear: true, cwd: current };
    if (name === "pwd")
      return { output: current || workspace?.name || "/", cwd: current };
    const resolve = (value) => {
      const parts = (value || "").startsWith("/")
        ? value.split("/")
        : [...current.split("/"), ...(value || ".").split("/")];
      const result = [];
      for (const part of parts) {
        if (!part || part === ".") continue;
        if (part === "..") result.pop();
        else result.push(part);
      }
      return result.join("/");
    };
    if (name === "cd") {
      const target = resolve(parts.join(" "));
      let handle = workspaceManager.root;
      try {
        for (const part of target.split("/").filter(Boolean))
          handle = await handle.getDirectoryHandle(part);
        setTerminalSession((session) => ({
          ...session,
          currentWorkingDirectory: target,
        }));
        return { output: "", cwd: target };
      } catch {
        return {
          output: `ERROR: Directory "${parts.join(" ") || "."}" not found.`,
          cwd: current,
        };
      }
    }
    if (name === "ls" || name === "dir") {
      let handle = workspaceManager.root;
      try {
        for (const part of current.split("/").filter(Boolean))
          handle = await handle.getDirectoryHandle(part);
        const entries = [];
        for await (const item of handle.values())
          entries.push(
            `${item.kind === "directory" ? "[DIR] " : "      "}${item.name}`,
          );
        return { output: entries.join("\n"), cwd: current };
      } catch {
        return {
          output: "ERROR: Cannot read the current directory.",
          cwd: current,
        };
      }
    }
    return {
      output: "ERROR: Native shell commands require the Electron desktop app.",
      cwd: current,
    };
  };
  const sync = async () => {
    const result = await workspaceManager.refresh();
    const nodes = childrenOf(result);
    setTree(normalize(nodes));
    return nodes;
  };
  const openFolder = async () => {
    try {
      const result = await workspaceManager.open();
      await activateWorkspace(result);
    } catch (err) {
      setOutput((lines) => [...lines, err.message]);
    }
  };
  const previewAssistantHtml = ({ prompt, content }) => {
    if (
      !/\b(run|open|preview|launch)\b/i.test(prompt) ||
      !/\b(html|webpage|website|browser)\b/i.test(prompt)
    )
      return;
    const block = codeBlocks(content).find(
      (item) =>
        item.language === "html" ||
        /<\s*!doctype\s+html|<\s*html/i.test(item.content),
    );
    if (!block) return;
    const url = URL.createObjectURL(
      new Blob([block.content], { type: "text/html" }),
    );
    window.open(url, "_blank", "noopener,noreferrer");
    setOutput((lines) => [
      ...lines.slice(-30),
      "Opened generated HTML preview in a new browser tab.",
    ]);
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  };
  const runAssistantCommand = async ({ prompt }) => {
    const match = String(prompt || "").match(
      /\brun\s+(?:(?:the|this)\s+)?(?:command\s+)?([a-z][\w.-]*(?:\s+[^\n]+)?)/i,
    );
    const command = match?.[1]?.trim();
    if (
      !command ||
      /^(it|this|the html|the file)$/i.test(command) ||
      !window.tokenpilotDesktop?.terminal?.execute ||
      !terminalSession
    )
      return;
    const result = await window.tokenpilotDesktop.terminal.execute(
      terminalSession.sessionId,
      command,
    );
    setOutput((lines) => [
      ...lines.slice(-30),
      `${terminalSession.currentWorkingDirectory || terminalSession.workspacePath}> ${command}`,
      result.output || "(no output)",
    ]);
    if (result.ok !== false)
      setTerminalSession((current) => ({
        ...current,
        currentWorkingDirectory: result.cwd || current.currentWorkingDirectory,
      }));
  };
  const startAssistantServers = ({ prompt }) => {
    if (!terminalSession || !window.tokenpilotDesktop?.terminal?.write) return;
    const request = String(prompt || "").toLowerCase();
    const commands = [];
    if (
      /(frontend|front-end|client).*(server|dev|development)|server.*frontend/.test(
        request,
      )
    )
      commands.push(
        "Start-Process powershell -ArgumentList '-NoExit','-Command','Set-Location Frontend; npm run dev'",
      );
    if (
      /(backend|back-end|api).*(server|dev|development)|server.*backend/.test(
        request,
      )
    )
      commands.push(
        "Start-Process powershell -ArgumentList '-NoExit','-Command','Set-Location Backend; uvicorn app.main:app --reload'",
      );
    if (!commands.length) return;
    commands.forEach((command) =>
      window.tokenpilotDesktop.terminal.write(
        terminalSession.sessionId,
        `${command}\r`,
      ),
    );
    setOutput((lines) => [
      ...lines.slice(-30),
      ...commands.map((command) => `Started: ${command}`),
    ]);
  };
  const closeFolder = async () => {
    await workspaceManager.close?.();
    setWorkspace(null);
    setTree([]);
    setExpanded(new Set());
    setTabs([]);
    setActiveId();
    setTerminalSession(null);
    setOutput(["Open a folder to start a workspace terminal."]);
  };
  const toggle = async (folder) => {
    console.debug("Explorer toggle", folder.path);
    setExpanded((current) => {
      const next = new Set(current);
      next.has(folder.id) ? next.delete(folder.id) : next.add(folder.id);
      return next;
    });
    if (!folder.children.length) await sync();
  };
  const open = async (file) => {
    const content = file.content ?? (await workspaceManager.read(file));
    const tab = {
      ...file,
      content,
      language: languageFor(file.name),
      dirty: false,
    };
    setTabs((current) =>
      current.some((item) => item.id === tab.id)
        ? current.map((item) => (item.id === tab.id ? tab : item))
        : [...current, tab],
    );
    setActiveId(tab.id);
  };
  const createFromAssistant = async ({ prompt, content }) => {
    const blocks = codeBlocks(content);
    if (!blocks.length) return;
    if (!workspaceManager.root) {
      setOutput((lines) => [
        ...lines.slice(-30),
        "AI generated code, but no workspace folder is open. Open a folder to create files automatically.",
      ]);
      return;
    }
    const created = [];
    for (const block of blocks) {
      const name = fileNameFromPrompt(prompt, block.language);
      const nodes = childrenOf(await workspaceManager.refresh());
      const existing = nodes.find(
        (node) => !node.isDirectory && node.path === name,
      );
      if (existing) await workspaceManager.write(existing, block.content);
      else
        await workspaceManager.createFile(
          { path: "", handle: workspaceManager.root },
          name,
          block.content,
        );
      created.push(name);
    }
    const result = await sync();
    const first = result?.find?.(
      (node) => !node.isDirectory && created.includes(node.name),
    );
    if (first) await open(first);
    setOutput((lines) => [
      ...lines.slice(-30),
      `AI created ${created.join(", ")}`,
    ]);
  };
  const save = async (tab) => {
    if (!tab) return;
    await workspaceManager.write(tab, tab.content);
    setTabs((current) =>
      current.map((item) =>
        item.id === tab.id ? { ...item, dirty: false } : item,
      ),
    );
    setOutput((lines) => [...lines.slice(-30), `Saved ${tab.path}`]);
  };
  const change = (content) => {
    if (!active) return;
    const tab = { ...active, content: content || "", dirty: true };
    setTabs((current) =>
      current.map((item) => (item.id === tab.id ? tab : item)),
    );
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(
      () =>
        save(tab).catch((err) => setOutput((lines) => [...lines, err.message])),
      700,
    );
  };
  const create = async (kind) => {
    if (!workspace) return openFolder();
    const name = window.prompt(
      kind === "folder" ? "Folder name" : "File name",
      kind === "folder" ? "src" : "untitled.js",
    );
    if (!name?.trim()) return;
    const root = { path: "", handle: workspaceManager.root };
    if (kind === "folder")
      await workspaceManager.createFolder(root, name.trim());
    else await workspaceManager.createFile(root, name.trim());
    await sync();
  };
  const closeTab = (id) => {
    const tab = tabs.find((item) => item.id === id);
    if (tab?.dirty && !window.confirm(`Discard changes to ${tab.name}?`))
      return;
    const next = tabs.filter((item) => item.id !== id);
    setTabs(next);
    if (activeId === id) setActiveId(next.at(-1)?.id);
  };
  useEffect(() => {
    const saveLayout = () => {
      localStorage.setItem("ide-left-width", String(left));
      localStorage.setItem("ide-right-width", String(right));
      localStorage.setItem("ide-bottom-height", String(bottomHeight));
      localStorage.setItem("ide-left-closed", leftClosed ? "1" : "0");
      localStorage.setItem("ide-right-closed", rightClosed ? "1" : "0");
    };
    saveLayout();
    editorRef.current?.layout();
  }, [left, right, bottomHeight, leftClosed, rightClosed, bottomOpen]);
  useEffect(() => {
    const move = (event) => {
      if (!drag) return;
      const rect = rootRef.current?.getBoundingClientRect();
      if (!rect) return;
      if (drag === "left")
        setLeft(clamp(event.clientX - rect.left - 48, 180, 420));
      if (drag === "right")
        setRight(clamp(rect.right - event.clientX, 280, 600));
      if (drag === "bottom")
        setBottomHeight(
          clamp(
            rect.bottom - event.clientY,
            150,
            Math.round(rect.height * 0.6),
          ),
        );
    };
    const up = () => setDrag(null);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [drag]);
  useEffect(() => {
    const key = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
        event.preventDefault();
        setLeftClosed((value) => !value);
      }
      if (event.ctrlKey && event.altKey && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setRightClosed((value) => !value);
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        save(active);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [active]);
  useEffect(() => {
    const execute = async (event) => {
      const input = event.target;
      if (event.key !== "Enter" || !input.matches?.(".ide-console input"))
        return;
      event.preventDefault();
      event.stopPropagation();
      const command = input.value.trim();
      input.value = "";
      if (!terminalSession) {
        setOutput((lines) => [
          ...lines,
          "ERROR: Open a workspace before executing commands.",
        ]);
        return;
      }
      try {
        const result = window.tokenpilotDesktop?.terminal?.execute
          ? await window.tokenpilotDesktop.terminal.execute(
              terminalSession.sessionId,
              command,
            )
          : await browserTerminal(command);
        if (result.clear) {
          setOutput([`${result.cwd || ""}>`]);
          return;
        }
        setOutput((lines) =>
          [
            ...lines,
            `${terminalSession.currentWorkingDirectory || terminalSession.workspacePath}> ${command}`,
            result.output,
            `${result.cwd || terminalSession.currentWorkingDirectory || terminalSession.workspacePath}>`,
          ].filter(Boolean),
        );
        if (result.ok !== false)
          setTerminalSession((current) => ({
            ...current,
            currentWorkingDirectory:
              result.cwd || current.currentWorkingDirectory,
          }));
      } catch (error) {
        setOutput((lines) => [...lines, `ERROR: ${error.message}`]);
      }
    };
    document.addEventListener("keydown", execute, true);
    return () => document.removeEventListener("keydown", execute, true);
  }, [terminalSession, workspace]);
  useEffect(() => {
    if (!workspace) return;
    workspaceManager
      .context()
      .then((context) => {
        window.tokenpilotWorkspaceContext = context;
      })
      .catch(() => {});
  }, [workspace, tree]);
  useEffect(() => {
    const closeShortcut = (event) => {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key.toLowerCase() === "w" &&
        workspace
      ) {
        event.preventDefault();
        closeFolder();
      }
    };
    window.addEventListener("keydown", closeShortcut);
    return () => window.removeEventListener("keydown", closeShortcut);
  }, [workspace]);
  useEffect(() => {
    const host = document.querySelector(".ide-explorer-v2 header div");
    if (!host) return;
    host
      .querySelectorAll("[data-workspace-action]")
      .forEach((button) => button.remove());
    if (!workspace) return;
    const switchButton = document.createElement("button");
    switchButton.type = "button";
    switchButton.dataset.workspaceAction = "switch";
    switchButton.title = "Switch folder";
    switchButton.textContent = "Switch";
    switchButton.onclick = openFolder;
    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.dataset.workspaceAction = "close";
    closeButton.title = "Close workspace";
    closeButton.textContent = "Close";
    closeButton.onclick = closeFolder;
    host.insertBefore(switchButton, host.firstChild);
    host.insertBefore(closeButton, host.firstChild);
    return () =>
      host
        .querySelectorAll("[data-workspace-action]")
        .forEach((button) => button.remove());
  }, [workspace]);
  useEffect(() => {
    const handleAssistantResponse = (event) => {
      createFromAssistant(event.detail).catch((error) =>
        setOutput((lines) => [
          ...lines,
          `AI file creation failed: ${error.message}`,
        ]),
      );
    };
    window.addEventListener(
      "tokenpilot:assistant-response",
      handleAssistantResponse,
    );
    return () =>
      window.removeEventListener(
        "tokenpilot:assistant-response",
        handleAssistantResponse,
      );
  }, [workspace]);
  useEffect(() => {
    const handlePreview = (event) => previewAssistantHtml(event.detail);
    window.addEventListener("tokenpilot:assistant-response", handlePreview);
    return () =>
      window.removeEventListener(
        "tokenpilot:assistant-response",
        handlePreview,
      );
  }, [workspace]);
  useEffect(() => {
    const handleCommand = (event) => {
      runAssistantCommand(event.detail).catch((error) =>
        setOutput((lines) => [...lines, `AI command failed: ${error.message}`]),
      );
    };
    window.addEventListener("tokenpilot:assistant-response", handleCommand);
    return () =>
      window.removeEventListener(
        "tokenpilot:assistant-response",
        handleCommand,
      );
  }, [workspace, terminalSession]);
  useEffect(() => {
    const handleServers = (event) => startAssistantServers(event.detail);
    window.addEventListener("tokenpilot:assistant-response", handleServers);
    return () =>
      window.removeEventListener(
        "tokenpilot:assistant-response",
        handleServers,
      );
  }, [workspace, terminalSession]);
  useEffect(() => {
    const resize = () => editorRef.current?.layout();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  useEffect(() => () => clearTimeout(saveTimer.current), []);
  const style = {
    "--ide-left": leftClosed ? "52px" : `${left}px`,
    "--ide-right": rightClosed ? "52px" : `${right}px`,
    "--ide-bottom": bottomOpen ? `${bottomHeight}px` : "34px",
  };
  return (
    <div
      className={`ide-reference-shell ${drag ? "is-dragging" : ""}`}
      ref={rootRef}
    >
      <header className="ide-product-bar">
        <div className="ide-brand">
          <Code2 size={18} />
          <b>TokenPilot IDE</b>
          <span>AI Workspace</span>
          <em>/</em>
          <strong>{workspace?.name || "No folder open"}</strong>
        </div>
        <label>
          <Search size={15} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter files"
          />
        </label>
      </header>
      <div className="ide-reference-body">
        <aside className="ide-activity-rail">
          <button
            className="active"
            onClick={() => setLeftClosed(false)}
            title="Explorer (Ctrl+B)"
          >
            <FolderOpen size={19} />
          </button>
          <button
            onClick={() => setRightClosed(false)}
            title="AI Assistant (Ctrl+Alt+A)"
          >
            <Bot size={19} />
          </button>
          <button onClick={() => setBottomOpen(true)} title="Terminal">
            <PanelBottom size={19} />
          </button>
        </aside>
        <div className="ide-split-layout" style={style}>
          <aside className={`ide-explorer-v2 ${leftClosed ? "collapsed" : ""}`}>
            <div
              className="ide-splitter left"
              onMouseDown={() => !leftClosed && setDrag("left")}
              onDoubleClick={() => setLeft(240)}
            />
            <header>
              <span>
                <FolderOpen size={16} />
                <b>Explorer</b>
              </span>
              <div>
                <button onClick={openFolder} title="Open folder">
                  <FolderOpen size={16} />
                </button>
                <button onClick={() => create("file")} title="New file">
                  <FilePlus2 size={16} />
                </button>
                <button onClick={() => create("folder")} title="New folder">
                  <FolderPlus size={16} />
                </button>
                <button
                  onClick={() => setLeftClosed((value) => !value)}
                  title="Collapse Explorer"
                >
                  <ChevronLeft size={16} />
                </button>
              </div>
            </header>
            {!leftClosed && (
              <>
                <button className="ide-open-folder" onClick={openFolder}>
                  Open Folder
                </button>
                <label className="ide-file-search">
                  <Search size={14} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Filter files"
                  />
                </label>
                <div className="ide-section-title">
                  <ChevronDown size={14} /> {workspace?.name || "WORKSPACE"}
                </div>
                <div className="ide-file-tree">
                  <Tree
                    nodes={tree}
                    expanded={expanded}
                    toggle={toggle}
                    open={open}
                    filter={query}
                  />
                </div>
              </>
            )}
          </aside>
          <main className="ide-center">
            <header className="ide-tabs-v2">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  className={tab.id === activeId ? "active" : ""}
                  onClick={() => setActiveId(tab.id)}
                >
                  {tab.dirty && "●"} <FileCode2 size={14} />
                  {tab.name}
                  <X
                    size={13}
                    onClick={(event) => {
                      event.stopPropagation();
                      closeTab(tab.id);
                    }}
                  />
                </button>
              ))}
            </header>
            <section className="ide-editor-v2">
              {active ? (
                <Suspense
                  fallback={
                    <div className="ide-editor-loading">Loading editor…</div>
                  }
                >
                  <MonacoEditor
                    height="100%"
                    theme="vs-dark"
                    language={active.language}
                    value={active.content}
                    onMount={(editor) => {
                      editorRef.current = editor;
                      editor.layout();
                    }}
                    onChange={change}
                    options={{
                      minimap: { enabled: true },
                      automaticLayout: true,
                      wordWrap: "on",
                      folding: true,
                      fontSize: 14,
                    }}
                  />
                </Suspense>
              ) : (
                <div className="ide-welcome">
                  <Code2 size={34} />
                  <h2>
                    {workspace
                      ? "Open a file to start building"
                      : "Open a local project folder"}
                  </h2>
                  <button onClick={openFolder}>Open Folder</button>
                </div>
              )}
            </section>
            <section className="ide-bottom">
              <div
                className="ide-splitter bottom"
                onMouseDown={() => setDrag("bottom")}
              />
              <header>
                {["terminal", "output", "problems", "logs"].map((item) => (
                  <button
                    key={item}
                    className={bottom === item ? "active" : ""}
                    onClick={() => {
                      setBottom(item);
                      setBottomOpen(true);
                    }}
                  >
                    {item === "terminal" && <Terminal size={13} />} {item}
                  </button>
                ))}
                <button
                  className="ide-panel-toggle"
                  onClick={() => setBottomOpen((value) => !value)}
                >
                  {bottomOpen ? (
                    <ChevronDown size={15} />
                  ) : (
                    <ChevronRight size={15} />
                  )}
                </button>
              </header>
              {bottomOpen && (
                <div className="ide-console">
                  <pre>{output.join("\n")}</pre>
                  {bottom === "terminal" && (
                    <input placeholder="Terminal input…" />
                  )}
                </div>
              )}
            </section>
          </main>
          <aside className={`ide-ai-panel ${rightClosed ? "collapsed" : ""}`}>
            <div
              className="ide-splitter right"
              onMouseDown={() => !rightClosed && setDrag("right")}
              onDoubleClick={() => setRight(340)}
            />
            <header>
              <span>
                <Bot size={17} />
                <b>TokenPilot AI</b>
              </span>
              <button
                onClick={() => setRightClosed((value) => !value)}
                title="Collapse AI Assistant"
              >
                {rightClosed ? (
                  <ChevronLeft size={16} />
                ) : (
                  <ChevronRight size={16} />
                )}
              </button>
            </header>
            {!rightClosed && (
              <>
                <div className="ide-ai-context">
                  <span>
                    {active?.path || workspace?.name || "No workspace"}
                  </span>
                  <small>Current workspace / file context</small>
                </div>
                <AIChat embedded />
              </>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}
