import { useEffect, useRef, useState } from 'react'
import { Bot, Info, Pencil, Share2, X } from 'lucide-react'
import { workspaceApi } from '../../services/api'
import ConversationSidebar from './components/ConversationSidebar'
import ProviderSwitcher from './components/ProviderSwitcher'
import MessageList from './components/MessageList'
import Composer from './components/Composer'
import CommandWorkflow, { parseCommands } from './components/CommandWorkflow'
import './chat.css'
import './chat-functional.css'
import './chat-scroll-fix.css'
import './chat-images.css'
import './chat-controls.css'

const prompts = ['Explain', 'Fix', 'Refactor', 'Tests', 'Review', 'Optimize', 'Generate docs']

const providerErrorText = error => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.errors?.length) return detail.errors.join(' ')
  if (detail?.message) return detail.message
  if (detail?.response_body?.error?.message) return `${detail.provider || 'AI provider'}: ${detail.response_body.error.message}`
  if (detail?.response_body?.message) return `${detail.provider || 'AI provider'}: ${detail.response_body.message}`
  if (detail?.provider && detail?.status) return `${detail.provider} request failed (${detail.status}). Check the API key and model configuration.`
  return 'The selected provider could not complete the request. Please try again.'
}

function KeySetup({ onDone, onCancel }) {
  const [form, setForm] = useState({ provider:'OpenAI', model:'gpt-4o-mini', api_key:'' }); const [saving, setSaving] = useState(false); const [error, setError] = useState('')
  const save = async event => { event.preventDefault(); setSaving(true); try { await workspaceApi.personalKey(form); await onDone() } catch (requestError) { setError(requestError.response?.data?.detail || 'Could not save the provider connection.') } finally { setSaving(false) } }
  return <div className="tp-modal-backdrop"><form className="tp-key-setup" onSubmit={save}><header><h2>Add provider connection</h2>{onCancel && <button type="button" onClick={onCancel}><X size={16}/></button>}</header><label>Provider<select value={form.provider} onChange={event => setForm(current => ({ ...current, provider:event.target.value, model:event.target.value === 'Gemini' ? 'gemini-3.6-flash' : 'gpt-4o-mini' }))}><option>OpenAI</option><option>Gemini</option><option>Claude</option><option>Groq</option></select></label><label>Model<input value={form.model} onChange={event => setForm(current => ({ ...current, model:event.target.value }))} required/></label><label>API key<input type="password" value={form.api_key} onChange={event => setForm(current => ({ ...current, api_key:event.target.value }))} required/></label>{error && <small className="tp-form-error">{String(error)}</small>}<footer>{onCancel && <button type="button" onClick={onCancel}>Cancel</button>}<button className="tp-primary" disabled={saving}>{saving ? 'Saving…' : 'Save connection'}</button></footer></form></div>
}

function EmptyState({ onPrompt, inputRef }) {
  return <div className="tp-empty"><div className="tp-empty-icon"><Bot size={19}/></div><span>TOKENPILOT AI</span><h1>How can I help you today?</h1><div>{prompts.map(prompt => <button key={prompt} onClick={() => { onPrompt(prompt); inputRef.current?.focus() }}>{prompt}</button>)}</div></div>
}

export default function ChatWorkspace({ embedded = false, initialPrompt = '' }) {
  const [connections, setConnections] = useState({ personal: [], organization: [] })
  const [selected, setSelected] = useState()
  const [chats, setChats] = useState([])
  const [chat, setChat] = useState()
  const [search, setSearch] = useState('')
  const [prompt, setPrompt] = useState(initialPrompt)
  const [images, setImages] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [cacheCandidate, setCacheCandidate] = useState(null)
  const [keySetup, setKeySetup] = useState(false)
  const [workflow, setWorkflow] = useState({ commands: [], statuses: {} })
  const bottomRef = useRef()
  const inputRef = useRef()

  const loadConnections = async () => { const response = await workspaceApi.connections(); const next = response.data || { personal: [], organization: [] }; setConnections(next); setSelected(current => [...next.organization, ...next.personal].find(item => item.id === current?.id) || next.organization[0] || next.personal[0]) }
  const loadChats = async value => { const response = await workspaceApi.chats(value); setChats(response.data || []) }
  const createChat = async () => { const response = await workspaceApi.createChat(); setChat({ ...response.data, messages: [] }); inputRef.current?.focus() }
  const openChat = async id => { const response = await workspaceApi.chat(id); setChat(response.data); setCacheCandidate(null) }
  const send = async (forced, options = {}) => {
    const content = (forced ?? prompt).trim(); if ((!content && !images.length) || loading) return
    if (!selected) { setError('Add a provider connection before sending a request.'); return }
    let target = chat
    if (!target) { const response = await workspaceApi.createChat(); target = response.data; setChat({ ...target, messages: [] }) }
    const outgoingImages = forced === undefined ? images : []
    const outgoingDocuments = forced === undefined ? documents : []
    setPrompt(''); setImages([]); setDocuments([]); window.tokenpilotDocuments = []; setError(''); setCacheCandidate(null); setLoading(true)
    setChat(current => ({ ...current, messages:[...(current?.messages || []), { role:'user', content, images:outgoingImages }] }))
    try {
      const response = await workspaceApi.send(target.id, { content, images:outgoingImages.map(({ mime_type, data }) => ({ mime_type, data })), documents:outgoingDocuments, key_id:selected.id, key_source:selected.source, ...options })
      const answer = { ...response.data, provider:selected.label, model:selected.model }
      setChat(current => ({ ...current, title:current.title === 'New conversation' ? content.slice(0, 60) : current.title, messages:[...current.messages, answer] }))
      const commands = parseCommands(answer.content); if (commands.length) setWorkflow(current => ({ commands:[...current.commands, ...commands], statuses:{ ...current.statuses, ...Object.fromEntries(commands.map(item => [item.command, 'Pending'])) } }))
      await loadChats(search)
    } catch (requestError) {
      if (requestError.response?.status !== 409) {
        setChat(current => ({
          ...current,
          messages: (current?.messages || []).filter((message, index, messages) => !(index === messages.length - 1 && message.role === 'user' && message.content === content))
        }))
        setError(providerErrorText(requestError))
      }
    } finally { setLoading(false) }
  }
  const addImages = async files => { const valid = files.slice(0, 4 - images.length).filter(file => file.size <= 3 * 1024 * 1024); const encoded = await Promise.all(valid.map(file => new Promise(resolve => { const reader = new FileReader(); reader.onload = () => resolve({ name:file.name, mime_type:file.type, data:String(reader.result).split(',')[1] }); reader.readAsDataURL(file) }))); setImages(current => [...current, ...encoded]) }
  const importFile = file => { if (/\.(pdf|docx)$/i.test(file.name)) { const reader = new FileReader(); reader.onload = () => setDocuments(current => { const next = [...current.slice(-3), { name:file.name, mime_type:file.type || 'application/octet-stream', data:String(reader.result).split(',')[1] }]; window.tokenpilotDocuments = next; return next }); reader.readAsDataURL(file); return } const reader = new FileReader(); reader.onload = () => setPrompt(current => `${current}${current ? '\n\n' : ''}Please analyze this file (${file.name}):\n\n${String(reader.result).slice(0, 30000)}`); reader.readAsText(file) }
  const visibleChats = chats
  useEffect(() => { window.tokenpilotDocuments = documents }, [documents])
  useEffect(() => { Promise.all([loadConnections(), loadChats()]).catch(() => {}) }, [])
  useEffect(() => { const refresh = () => loadConnections().catch(() => {}); const error = event => setError(event.detail); window.addEventListener('tokenpilot:connections-changed', refresh); window.addEventListener('tokenpilot:connection-error', error); return () => { window.removeEventListener('tokenpilot:connections-changed', refresh); window.removeEventListener('tokenpilot:connection-error', error) } }, [])
  useEffect(() => { const timer = setTimeout(() => loadChats(search).catch(() => {}), 250); return () => clearTimeout(timer) }, [search])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth', block:'end' }) }, [chat?.messages?.length, loading, error])
  useEffect(() => { const handleCache = event => setCacheCandidate(event.detail); window.addEventListener('tokenpilot:cache-candidate', handleCache); return () => window.removeEventListener('tokenpilot:cache-candidate', handleCache) }, [])

  if (keySetup) return <KeySetup onDone={async () => { setKeySetup(false); await loadConnections() }} onCancel={selected ? () => setKeySetup(false) : null}/>
  const latestCommand = workflow.commands.at(-1)
  return <div className={`tp-chat-app ${embedded ? 'embedded' : ''}`}><ConversationSidebar chats={visibleChats} activeId={chat?.id} search={search} onSearch={setSearch} onNew={createChat} onOpen={openChat} onRename={() => {}} onDelete={() => {}} onPin={() => {}} onArchive={() => {}} filter="all" onFilter={() => {}} provider={selected?.provider}/><main className="tp-chat-main"><header className="tp-chat-header"><div><b>{chat?.title || 'New chat'}</b>{chat && <button onClick={() => { const title = window.prompt('Rename conversation', chat.title); if (title?.trim()) workspaceApi.renameChat(chat.id, { title }).then(() => setChat(current => ({ ...current, title }))) }}><Pencil size={13}/></button>}</div><section><ProviderSwitcher selected={selected} companyKeys={connections.organization} personalKeys={connections.personal} onSelect={setSelected} onAdd={() => setKeySetup(true)} onManage={() => setKeySetup(true)}/><button title="Share conversation link" onClick={() => navigator.clipboard?.writeText(window.location.href)}><Share2 size={16}/></button><button title="Conversation info"><Info size={16}/></button></section></header><div className="tp-chat-body">{!chat?.messages?.length ? <EmptyState onPrompt={setPrompt} inputRef={inputRef}/> : <MessageList messages={chat.messages} loading={loading} onEdit={setPrompt} onRegenerate={send} bottomRef={bottomRef} commandStatuses={workflow.statuses} onCommandStatus={(command, status) => setWorkflow(current => ({ ...current, statuses:{ ...current.statuses, [command]:status } }))} cacheCandidate={cacheCandidate} onReuseCache={() => send(cacheCandidate.prompt, { reuse_cache:true, cache_id:cacheCandidate.id })} onFreshCache={() => setCacheCandidate(null)}/>} {latestCommand && <CommandWorkflow command={latestCommand} status={workflow.statuses[latestCommand.command] || 'Pending'} onStatus={status => setWorkflow(current => ({ ...current, statuses:{ ...current.statuses, [latestCommand.command]:status } }))} onAnalyze={logs => send(`Analyze the terminal output for command: ${latestCommand.command}\n\nTerminal output:\n${logs}`)}/>} {error && <div className="tp-chat-error">{String(error)}<button onClick={() => setError('')}><X size={14}/></button></div>}</div><Composer value={prompt} images={images} onChange={setPrompt} onImages={addImages} onRemoveImage={index => setImages(current => current.filter((_, itemIndex) => index !== itemIndex))} onSend={send} loading={loading} inputRef={inputRef} onTextFile={importFile}/></main></div>
}
