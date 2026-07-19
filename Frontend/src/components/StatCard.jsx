import { motion } from 'framer-motion'
export default function StatCard({ label, value, icon: Icon, tone = 'purple', detail }) { return <motion.div className="stat-card" whileHover={{ y: -3 }}><div className={`stat-icon ${tone}`}>{Icon && <Icon size={19}/>}</div><div><span className="muted">{label}</span><strong>{value ?? '—'}</strong>{detail && <small>{detail}</small>}</div></motion.div> }
