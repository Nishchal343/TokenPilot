import { Check, ChevronDown, CircleAlert, KeyRound, Plus, Settings2 } from 'lucide-react'
import { useState } from 'react'

const glyph = { OpenAI: '◎', Gemini: '✦', Claude: '◈', Anthropic: '◈', Groq: '⚡', OpenRouter: '◇', Ollama: '◉', DeepSeek: '◌', Mistral: 'M', xAI: '𝕏', Custom: '◇', Other: '◇' }
export const ProviderBadge = ({ provider }) => <span className="tp-provider-badge" title={provider}>{glyph[provider] || glyph.Custom}</span>

export default function ProviderSwitcher({ selected, companyKeys = [], personalKeys = [], onSelect, onAdd, onManage }) {
  const [open, setOpen] = useState(false)
  const choose = key => { onSelect(key); localStorage.setItem('tokenpilot_selected_connection', JSON.stringify({ id:key.id, source:key.source })); setOpen(false) }
  const option = key => <button className={`tp-connection-option ${selected?.source === key.source && selected?.id === key.id ? 'selected' : ''}`} key={`${key.source}-${key.id}`} onClick={() => choose(key)}><ProviderBadge provider={key.provider}/><span><b>{key.label}</b><small>{key.provider} · {key.model}</small></span><i className="tp-connection-status">Connected</i>{selected?.source === key.source && selected?.id === key.id && <Check size={15}/>}</button>
  const noKeys = !companyKeys.length && !personalKeys.length
  return <div className="tp-switcher"><button className={`tp-switcher-trigger ${!selected ? 'disconnected' : ''}`} onClick={() => setOpen(value => !value)}><span className="tp-live"/><ProviderBadge provider={selected?.provider}/><span><b>{selected?.label || 'Not connected'}</b><small>{selected ? `${selected.provider} · ${selected.model}` : 'Add a secure provider connection'}</small></span><ChevronDown size={15}/></button>{open && <><button className="tp-click-away" aria-label="Close provider menu" onClick={() => setOpen(false)}/><div className="tp-switcher-menu">{companyKeys.length > 0 && <><p>COMPANY API</p>{companyKeys.map(option)}</>}{personalKeys.length > 0 && <><p className="divider-label">YOUR API KEYS</p>{personalKeys.map(option)}</>}{noKeys && <div className="tp-no-connection"><CircleAlert size={15}/><span><b>Not connected</b><small>Add a provider to start chatting.</small></span></div>}<div className="tp-menu-divider"/><button onClick={() => { setOpen(false); onAdd() }}><Plus size={15}/> Add provider</button><button onClick={() => { setOpen(false); onManage() }}><Settings2 size={15}/> AI settings</button></div></>}</div>
}
