import { useState } from 'react'
import { ChevronDown, ChevronRight, HelpCircle } from 'lucide-react'

const FAQ_SECTIONS = [
  {
    section: 'Authentication',
    items: [
      ['How do I create a company account?', 'Click "Build your workspace" on the landing page. Fill in your company details, submit, and verify your email using the 6-digit OTP sent to your inbox.'],
      ['How do employees join?', 'Company admins or team leads send invitation emails. Employees receive a unique invitation link, click it, and register using that token.'],
      ['What should I do if I forget my password?', 'Click "Forgot password?" on the Sign In page. Enter your email address, receive an OTP, and use it to set a new password.'],
      ['How long do sessions last?', 'Sessions are managed via JWT tokens. Refreshing the browser maintains your session. Closing the browser and reopening will restore your session from localStorage.'],
    ],
  },
  {
    section: 'Invitations',
    items: [
      ['How do I invite a team member?', 'Navigate to the Invitations page, enter the email address, and click Send. The recipient receives an email with a registration link.'],
      ['Can employees invite other employees?', 'Team leads can invite employees under their hierarchy. Regular employees cannot send invitations.'],
      ['What happens if an invitation expires?', 'Invitations expire after the configured period (default 7 days). You can resend a new invitation to the same email.'],
    ],
  },
  {
    section: 'Organization Hierarchy',
    items: [
      ['How does the hierarchy work?', 'TokenPilot supports unlimited hierarchy levels. The company admin is at the top, followed by team leads, and then employees. Each level can have multiple sub-levels.'],
      ['Can an employee have multiple managers?', 'No. Each employee reports to exactly one manager or directly to the company. However, company admins can reassign managers.'],
      ['How do I promote an employee to team lead?', 'Visit the Organization page, find the employee, and use the promote action. They will gain team lead permissions.'],
    ],
  },
  {
    section: 'Token Budgets',
    items: [
      ['What are token budgets?', 'Token budgets control how many AI tokens each employee or team can use per month. They prevent unexpected cost overruns.'],
      ['Who sets token budgets?', 'Company admins can set budgets for all employees. Team leads can set budgets for employees in their subtree.'],
      ['What happens when a budget is exceeded?', 'Usage tracking displays the overage. The platform records all requests so admins can review usage patterns.'],
    ],
  },
  {
    section: 'Usage Tracking',
    items: [
      ['What AI models are tracked?', 'TokenPilot tracks GPT, Gemini, Claude, and other model requests through the token budget system.'],
      ['How is cost estimated?', 'Estimated cost is calculated based on token consumption with approximate per-token pricing for each supported model.'],
    ],
  },
  {
    section: 'Security',
    items: [
      ['Is my data secure?', 'Yes. All passwords are hashed with bcrypt. Authentication uses JWT tokens with configurable expiry. All API endpoints require valid tokens.'],
      ['Can I see who accessed my account?', 'Visit the Security page to see recent login history and account activity events.'],
    ],
  },
  {
    section: 'Password Reset',
    items: [
      ['How do I reset my password if I\'m logged in?', 'Go to Settings and use the Change Password form. You\'ll need your current password.'],
      ['What if I can\'t log in at all?', 'Use the "Forgot password?" link on the Sign In page to receive a reset OTP by email.'],
      ['How long is the reset OTP valid?', 'OTPs expire after 10 minutes. If yours has expired, simply request a new one.'],
    ],
  },
]

function FaqItem({ question, answer }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`faq-item ${open ? 'open' : ''}`}>
      <button className="faq-q" onClick={() => setOpen(!open)}>
        <span>{question}</span>
        {open ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}
      </button>
      {open && <p className="faq-a">{answer}</p>}
    </div>
  )
}

export default function HelpCenter() {
  return (
    <div className="help-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SUPPORT</div>
          <h1>Help Center</h1>
          <p className="muted">Find answers to common questions about TokenPilot.</p>
        </div>
      </div>

      <div className="help-layout">
        {FAQ_SECTIONS.map(({ section, items }) => (
          <div key={section} className="panel help-section">
            <div className="help-section-head">
              <HelpCircle size={17} className="muted"/>
              <h3>{section}</h3>
            </div>
            {items.map(([q, a]) => <FaqItem key={q} question={q} answer={a}/>)}
          </div>
        ))}
      </div>
    </div>
  )
}
