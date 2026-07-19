import { BookOpen } from 'lucide-react'

const DOCS = [
  {
    title: 'Platform Overview',
    content: `TokenPilot is an enterprise AI token management platform that helps organizations monitor, control, and optimize AI usage across teams and models. It provides centralized governance, budget enforcement, usage analytics, and role-based access control in one dashboard.`
  },
  {
    title: 'Company Dashboard',
    content: `The Company Dashboard gives company admins a bird's-eye view of total AI usage, token consumption, cost estimates, team size, active users, and pending invitations. Use the stats cards to understand high-level health, and the token consumer table to identify heavy users.`
  },
  {
    title: 'Employee Dashboard',
    content: `Employees see their own token usage, monthly budget allocation, remaining tokens, estimated cost, and AI request counts. The dashboard also shows which AI models have been used (GPT, Gemini, Claude, Other).`
  },
  {
    title: 'Organization Structure',
    content: `TokenPilot supports unlimited organizational hierarchy levels:\n\n• Company Admin — full control over all employees, budgets, and settings\n• Team Lead (Manager) — manages employees in their subtree, can invite and set sub-budgets\n• Employee — uses the platform within assigned budgets\n\nEach employee reports to exactly one parent node. The hierarchy can be as deep as needed.`
  },
  {
    title: 'Invitations',
    content: `Team members are added via email invitations. Company admins can invite both team leads and employees. Team leads can invite employees under their subtree. Each invitation contains a unique token that expires after 7 days. Employees register using this token.`
  },
  {
    title: 'Budgets',
    content: `Token budgets define the maximum number of AI tokens a user may consume per month. Company admins set budgets for all employees. Team leads can manage budgets for their direct reports. Budgets track: monthly limit, used tokens, remaining tokens, total AI requests, and estimated cost.`
  },
  {
    title: 'Notifications',
    content: `Notifications inform employees of important workspace events including: invitation accepted/rejected, budget updates, token limit changes, password changes, and system messages. Notifications can be marked as read individually or all at once. They can also be deleted.`
  },
  {
    title: 'JWT Authentication',
    content: `TokenPilot uses JSON Web Tokens (JWT) for stateless authentication. On login, a signed JWT is issued and stored in the browser's localStorage. Every API request automatically attaches the token as an Authorization: Bearer header. Tokens expire after the configured duration. If a token expires, the user is automatically redirected to Sign In.`
  },
  {
    title: 'Roles & Permissions',
    content: `• Company Admin — accesses all dashboards, employee management, all budgets, all invitations\n• Team Lead — accesses team dashboard, team budgets, team organization tree, can invite sub-employees\n• Employee — accesses personal dashboard, own budget, own organization view\n\nAll API endpoints enforce role-based access. Unauthorized access returns 403 Forbidden.`
  },
]

export default function Documentation() {
  return (
    <div className="docs-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SUPPORT</div>
          <h1>Documentation</h1>
          <p className="muted">Complete reference for the TokenPilot platform.</p>
        </div>
      </div>

      <div className="docs-layout">
        <nav className="docs-sidebar">
          {DOCS.map(d => (
            <a key={d.title} href={`#doc-${d.title.replace(/\s+/g, '-')}`} className="docs-nav-link">
              {d.title}
            </a>
          ))}
        </nav>

        <div className="docs-content">
          {DOCS.map(d => (
            <section key={d.title} id={`doc-${d.title.replace(/\s+/g, '-')}`} className="docs-section panel">
              <div className="docs-section-head">
                <BookOpen size={18} className="muted"/>
                <h2>{d.title}</h2>
              </div>
              {d.content.split('\n').map((line, i) => (
                line.startsWith('•')
                  ? <p key={i} className="docs-bullet">{line}</p>
                  : line
                    ? <p key={i}>{line}</p>
                    : <br key={i}/>
              ))}
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
