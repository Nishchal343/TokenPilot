import { Orbit } from 'lucide-react'
export default function Logo({ compact = false }) { return <div className="logo"><span className="logo-mark"><Orbit size={18}/></span>{!compact && <span>Token<span className="gradient-text">Pilot</span></span>}</div> }
