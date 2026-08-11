import { useRef, useState } from 'react'
import { AlertTriangle, Check, Clipboard, FileUp, Play, Send, X } from 'lucide-react'
import { formatCurrency } from '../../../utils/formatters'

const shellLanguages = new Set(['bash', 'sh', 'shell', 'zsh', 'powershell', 'ps', 'cmd', 'terminal', 'console', 'command'])
const modifiesPattern = /(^|\s)(npm\s+(install|i|uninstall|update|run\s+(build|dev|start))|pip\s+(install|uninstall)|uv\s+(add|remove|sync)|docker\s+(build|run|compose|rm)|git\s+(clone|checkout|reset|clean|merge|rebase|commit|push|pull)|rm\s|del\s|mkdir\s|touch\s|echo\s+.*>|>)/i

export function parseCommands(value) {
  const text = String(value || '')
  const found = []
  const fenced = /```([\w-]*)\s*\n([\s\S]*?)```/g
  for (const match of text.matchAll(fenced)) {
    const language = match[1].toLowerCase()
    const command = match[2].trim()
    if (!shellLanguages.has(language) || !command || command.includes('<!DOCTYPE') || command.includes('<html')) continue
    found.push({ command, purpose: purposeFor(text, match.index + match[0].length), modifies: modifiesPattern.test(command) })
  }
  if (!found.length) {
    const inline = text.match(/(?:run|execute)\s+(?:this\s+)?command\s*:\s*`([^`]+)`/i)
    if (inline) found.push({ command:inline[1].trim(), purpose:purposeFor(text, inline.index + inline[0].length), modifies:modifiesPattern.test(inline[1]) })
  }
  return found.filter((item, index, items) => items.findIndex(other => other.command === item.command) === index)
}

function purposeFor(text, offset) {
  const tail = text.slice(offset, offset + 220).replace(/[`*_]/g, ' ')
  const match = tail.match(/(?:purpose|to|this will|so that)\s*[:\-]?\s*([^\n.]+)/i)
  return match?.[1]?.trim() || 'Run this command and provide the terminal output for analysis.'
}

export function CommandCard({ item, status = 'Pending', onCopy, onStatus }) {
  const copied = status === 'Copied'
  return <section className="tp-command-card"><header><div><b>Run this command</b><span className={`tp-command-status ${status.toLowerCase()}`}>{status}</span></div>{item.modifies && <small className="tp-command-warning"><AlertTriangle size={13}/> This command may modify files or dependencies.</small>}</header><pre>{item.command}</pre><p>{item.purpose}</p><footer><button onClick={onCopy}>{copied ? <Check size={14}/> : <Clipboard size={14}/>} {copied ? 'Copied' : 'Copy command'}</button>{status !== 'Success' && <button onClick={() => onStatus?.('Running')}><Play size={14}/> Mark running</button>}</footer></section>
}

export function CacheCandidate({ candidate, onReuse, onFresh }) { if (!candidate) return null; return <section className="tp-cache-card"><b>💡 Smart Token Saver</b><p>A similar request was detected.</p><div><span>Similarity <strong>{candidate.similarity}%</strong></span><span>Estimated tokens saved <strong>{candidate.tokens_saved}</strong></span><span>Estimated cost saved <strong>{formatCurrency(candidate.cost_saved)}</strong></span></div><footer><button onClick={onReuse}>⚡ Save Tokens</button><button onClick={onFresh}>↻ Generate Fresh Response</button></footer></section> }

export default function CommandWorkflow({ command, status = 'Pending', onAnalyze, onStatus }) {
  const [logs, setLogs] = useState('')
  const [error, setError] = useState('')
  const input = useRef()
  const upload = event => { const file = event.target.files?.[0]; event.target.value = ''; if (!file) return; const reader = new FileReader(); reader.onload = () => setLogs(String(reader.result || '')); reader.readAsText(file) }
  const submit = () => { if (!logs.trim()) { setError('Paste the terminal output before analyzing it.'); return } setError(''); onStatus?.('Running'); onAnalyze(logs.trim()); setLogs('') }
  if (!command) return null
  return <div className="tp-command-workflow"><CommandCard item={command} status={status} onCopy={() => navigator.clipboard?.writeText(command.command)} onStatus={onStatus}/><div className="tp-log-request"><b>Run the command on your local machine and paste the terminal output below.</b><textarea ref={input} value={logs} onChange={event => setLogs(event.target.value)} placeholder="Paste terminal logs here…"/><div><label><FileUp size={14}/> Upload .txt log<input type="file" accept=".txt,.log,text/plain" onChange={upload}/></label><button onClick={submit}><Send size={14}/> Analyze output</button></div>{error && <small><X size={13}/> {error}</small>}</div></div>
}
