import { useEffect, useState } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, CalendarDays, CheckCheck, Clock3, Eye, EyeOff, Gauge, MoonStar, ShieldCheck, Sparkles, Target, UserCircle2 } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

type AuthState = {
  token: string
  user: { id: number; email: string; display_name: string }
}

type TaskItem = {
  id: number
  title: string
  description?: string
  category: string
  priority: string
  status: string
  start_time?: string | null
  due_date?: string | null
  estimated_duration: number
  actual_duration?: number | null
}

type Summary = {
  total_tasks: number
  completed_tasks: number
  pending_tasks: number
  overdue_tasks: number
  workload_by_day: { day: string; hours: number }[]
  priority_distribution: Record<string, number>
  weekly_trend: { week: string; tasks: number }[]
}

const defaultTaskForm = {
  title: '',
  description: '',
  category: 'General',
  priority: 'medium',
  status: 'not_started',
  start_time: '',
  due_date: '',
  estimated_duration: 60,
}

function getStoredAuth(): AuthState | null {
  const raw = localStorage.getItem('mirror_auth')
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function friendlyErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const value = error.message.toLowerCase()

    if (value.includes('failed to fetch') || value.includes('network') || value.includes('load failed')) {
      return 'We could not reach the MIRROR server. Please check your internet connection and try again in a moment.'
    }

    if (value.includes('incorrect email or password') || value.includes('invalid credentials') || value.includes('unauthorized')) {
      return 'That email or password is not correct. Please check your details and try again.'
    }

    if (value.includes('passwords do not match')) {
      return 'Your passwords do not match. Please retype them and try again.'
    }

    if (value.includes('user already exists')) {
      return 'An account with this email already exists. Try logging in instead.'
    }

    if (value.includes('could not validate credentials')) {
      return 'Your session has expired. Please log in again.'
    }

    return error.message
  }

  return 'Something went wrong. Please try again.'
}

async function apiFetch<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers || {})
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  try {
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: 'Request failed' }))
      const detail = typeof payload?.detail === 'string' ? payload.detail : 'Request failed'
      throw new Error(detail)
    }
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  } catch (error) {
    throw new Error(friendlyErrorMessage(error))
  }
}

function App() {
  const [auth, setAuth] = useState<AuthState | null>(() => getStoredAuth())

  useEffect(() => {
    if (auth) {
      localStorage.setItem('mirror_auth', JSON.stringify(auth))
    } else {
      localStorage.removeItem('mirror_auth')
    }
  }, [auth])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage auth={auth} onLogout={() => setAuth(null)} />} />
        <Route path="/login" element={<LoginPage onLogin={setAuth} />} />
        <Route path="/register" element={<RegisterPage onLogin={setAuth} />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/dashboard" element={<ProtectedRoute auth={auth}><Dashboard auth={auth!} /></ProtectedRoute>} />
        <Route path="/tasks" element={<ProtectedRoute auth={auth}><TasksPage auth={auth!} /></ProtectedRoute>} />
        <Route path="/calendar" element={<ProtectedRoute auth={auth}><CalendarPage auth={auth!} /></ProtectedRoute>} />
        <Route path="/simulations" element={<ProtectedRoute auth={auth}><SimulationPage auth={auth!} /></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute auth={auth}><ProfilePage auth={auth!} /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute auth={auth}><SettingsPage auth={auth!} /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  )
}

function ProtectedRoute({ auth, children }: { auth: AuthState | null; children: React.ReactNode }) {
  if (!auth) return <Navigate to="/login" replace />
  return <>{children}</>
}

function LandingPage({ auth, onLogout }: { auth: AuthState | null; onLogout: () => void }) {
  const navLinks = [
    { label: 'Overview', href: '#features' },
    { label: 'How it works', href: '#workflow' },
    { label: 'Security', href: '#security' },
  ]

  return (
    <div className="min-h-screen bg-stone-50 text-slate-900">
      <header className="mx-auto max-w-7xl px-6 py-6">
        <div className="flex items-center justify-between rounded-full border border-slate-200 bg-white/80 px-4 py-3 shadow-sm backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">M</div>
            <div>
              <p className="text-lg font-semibold tracking-[0.2em] text-slate-900">MIRROR</p>
            </div>
          </div>
          <nav className="hidden items-center gap-8 md:flex">
            {navLinks.map((link) => (
              <a key={link.label} href={link.href} className="text-sm text-slate-600 hover:text-slate-900">{link.label}</a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            {auth ? (
              <>
                <Link to="/dashboard" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium">Dashboard</Link>
                <button type="button" onClick={onLogout} className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white">Log out</button>
              </>
            ) : (
              <>
                <Link to="/login" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium">Log in</Link>
                <Link to="/register" className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white">Sign up</Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        <section className="mx-auto grid max-w-7xl gap-12 px-6 pb-16 pt-10 md:grid-cols-[1.1fr_0.9fr] md:pt-20">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-medium text-violet-700">
              <Sparkles size={14} /> Digital twin planning
            </div>
            <h1 className="max-w-xl text-5xl font-semibold tracking-tight text-slate-900 md:text-6xl">See the impact before you decide.</h1>
            <p className="mt-6 max-w-xl text-lg text-slate-600">
              MIRROR models your schedule, deadlines, and workload to show what really happens before you commit.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link to="/register" className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">Get started <ArrowRight size={16} /></Link>
              <Link to="/login" className="rounded-full border border-slate-200 bg-white px-6 py-3 text-sm font-medium">Log in</Link>
            </div>
            <div className="mt-10 grid max-w-lg grid-cols-3 gap-4 text-sm text-slate-600">
              <div className="rounded-2xl border border-slate-200 bg-white p-4"><div className="text-2xl font-semibold text-slate-900">12k+</div><div>Simulations</div></div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4"><div className="text-2xl font-semibold text-slate-900">94%</div><div>Conflict spotted early</div></div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4"><div className="text-2xl font-semibold text-slate-900">2 min</div><div>To model a plan</div></div>
            </div>
          </div>

          <div className="rounded-[32px] border border-slate-200 bg-white p-5 shadow-[0_30px_80px_rgba(15,23,42,0.08)]">
            <div className="mb-4 flex items-center justify-between rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-700">
              <div className="flex items-center gap-2"><Clock3 size={16} /> What-if simulator</div>
              <span className="rounded-full bg-violet-100 px-2 py-1 text-xs font-medium text-violet-700">Before vs After</span>
            </div>
            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="mb-2 flex items-center justify-between text-sm"><span>Original plan</span><span className="text-slate-500">8.4h</span></div>
                <div className="space-y-2">
                  <div className="h-2.5 rounded-full bg-slate-200"><div className="h-full w-[70%] rounded-full bg-slate-900" /></div>
                  <div className="h-2.5 rounded-full bg-slate-200"><div className="h-full w-[60%] rounded-full bg-violet-500" /></div>
                </div>
              </div>
              <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
                <div className="mb-2 flex items-center justify-between text-sm"><span>Proposed plan</span><span className="text-violet-700">9.1h</span></div>
                <div className="space-y-2">
                  <div className="h-2.5 rounded-full bg-violet-100"><div className="h-full w-[80%] rounded-full bg-violet-600" /></div>
                  <div className="h-2.5 rounded-full bg-violet-100"><div className="h-full w-[50%] rounded-full bg-teal-500" /></div>
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-sm text-slate-500">Impact summary</p>
                <p className="mt-2 text-xl font-semibold text-slate-900">2 conflicts resolved · 1 deadline at risk</p>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="mx-auto max-w-7xl px-6 py-20">
          <div className="mb-10 max-w-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Why MIRROR</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900">Clarity for the decisions that actually change your day.</h2>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {[
              { icon: Gauge, title: 'Live schedule model', text: 'Track your time, deadlines, and conflicts as a living digital twin.' },
              { icon: Target, title: 'What-if testing', text: 'Simulate postponements, added tasks, and priority shifts without affecting real plans.' },
              { icon: ShieldCheck, title: 'Intentional approvals', text: 'Only apply changes after the user confirms the proposed schedule.' },
            ].map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-700"><Icon size={20} /></div>
                <h3 className="text-xl font-semibold text-slate-900">{title}</h3>
                <p className="mt-3 text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="workflow" className="bg-slate-900 py-20 text-white">
          <div className="mx-auto max-w-7xl px-6">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violet-300">How it works</p>
            <div className="mt-8 grid gap-8 md:grid-cols-3">
              {[
                'Build your personal schedule.',
                'Simulate a decision.',
                'Compare outcomes and choose your plan.',
              ].map((step, index) => (
                <div key={step} className="rounded-3xl border border-slate-700 bg-slate-800 p-6">
                  <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-full bg-violet-500 font-semibold">0{index + 1}</div>
                  <p className="text-lg font-medium text-white">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="mx-auto max-w-7xl px-6 py-20">
          <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
            <div className="grid gap-8 md:grid-cols-[1fr_0.9fr]">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-teal-600">Privacy and security</p>
                <h3 className="mt-3 text-3xl font-semibold text-slate-900">Your schedule stays yours — and only yours.</h3>
                <p className="mt-4 text-slate-600">MIRROR uses secure password hashing, authenticated requests, and explicit approval before changes touch your real calendar.</p>
              </div>
              <div className="space-y-3 rounded-2xl bg-slate-50 p-5">
                <div className="flex items-center gap-3"><ShieldCheck className="text-violet-700" size={20} /> Password protected accounts</div>
                <div className="flex items-center gap-3"><MoonStar className="text-violet-700" size={20} /> Theme and notification controls</div>
                <div className="flex items-center gap-3"><CheckCheck className="text-violet-700" size={20} /> Planned changes require confirmation</div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8 md:flex-row md:items-center md:justify-between">
          <div className="font-semibold tracking-[0.2em] text-slate-900">MIRROR</div>
          <div className="flex gap-6 text-sm text-slate-600">
            <a href="#features">Features</a>
            <a href="#workflow">Workflow</a>
            <a href="#security">Security</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

function PasswordField({
  label,
  name,
  autoComplete,
  placeholder,
}: {
  label: string
  name: string
  autoComplete?: string
  placeholder?: string
}) {
  const [showPassword, setShowPassword] = useState(false)

  return (
    <label className="block text-sm text-slate-600">
      {label}
      <div className="relative mt-2">
        <input
          name={name}
          type={showPassword ? 'text' : 'password'}
          autoComplete={autoComplete}
          placeholder={placeholder}
          required
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-11 outline-none ring-0 transition focus:border-violet-500 focus:bg-white"
        />
        <button
          type="button"
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          onClick={() => setShowPassword((value) => !value)}
          className="absolute inset-y-0 right-3 flex items-center text-slate-500 hover:text-slate-800"
        >
          {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </label>
  )
}

function ForgotPasswordPage() {
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') || '').trim()

    if (!email) {
      setError('Please enter your email address.')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Unable to send reset instructions')
      setSuccess(result.message || 'If an account exists for this email, reset instructions were sent.')
    } catch (err) {
      setError(friendlyErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
      <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-8 shadow-lg">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Password help</p>
        <h2 className="mt-3 text-3xl font-semibold text-slate-900">Forgot your password?</h2>
        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <label className="block text-sm text-slate-600">
            Email address
            <input name="email" type="email" required className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none ring-0 transition focus:border-violet-500 focus:bg-white" placeholder="you@example.com" />
          </label>
          {error && <p aria-live="polite" className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          {success && <p aria-live="polite" className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>}
          <button type="submit" disabled={loading} className="w-full rounded-full bg-slate-900 px-6 py-3 font-medium text-white disabled:opacity-60">
            {loading ? 'Sending...' : 'Send reset link'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          <Link to="/login" className="font-medium text-violet-700">Back to login</Link>
        </p>
      </div>
    </div>
  )
}

function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const initialEmail = searchParams.get('email') || ''
  const initialToken = searchParams.get('token') || ''

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') || '').trim()
    const token = String(form.get('token') || '').trim()
    const password = String(form.get('password') || '')
    const confirm = String(form.get('password_confirm') || '')

    if (!email || !token || !password || !confirm) {
      setError('Please complete all fields.')
      return
    }

    if (password !== confirm) {
      setError('Passwords do not match. Please retype them.')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`${API_BASE}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, token, password, password_confirm: confirm }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Password reset failed')
      setSuccess(result.message || 'Password reset successfully.')
      setTimeout(() => navigate('/login'), 1200)
    } catch (err) {
      setError(friendlyErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
      <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-8 shadow-lg">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Secure reset</p>
        <h2 className="mt-3 text-3xl font-semibold text-slate-900">Reset your password</h2>
        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <label className="block text-sm text-slate-600">
            Email address
            <input name="email" type="email" defaultValue={initialEmail} required className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none ring-0 transition focus:border-violet-500 focus:bg-white" placeholder="you@example.com" />
          </label>
          <label className="block text-sm text-slate-600">
            Reset token
            <input name="token" type="text" defaultValue={initialToken} required className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none ring-0 transition focus:border-violet-500 focus:bg-white" placeholder="Paste the reset token from the email" />
          </label>
          <PasswordField label="New password" name="password" autoComplete="new-password" placeholder="Enter a new password" />
          <PasswordField label="Confirm password" name="password_confirm" autoComplete="new-password" placeholder="Confirm your new password" />
          {error && <p aria-live="polite" className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          {success && <p aria-live="polite" className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>}
          <button type="submit" disabled={loading} className="w-full rounded-full bg-slate-900 px-6 py-3 font-medium text-white disabled:opacity-60">
            {loading ? 'Resetting...' : 'Reset password'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          <Link to="/login" className="font-medium text-violet-700">Back to login</Link>
        </p>
      </div>
    </div>
  )
}

function LoginPage({ onLogin }: { onLogin: (auth: AuthState) => void }) {
  const navigate = useNavigate()
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') || '').trim()
    const password = String(form.get('password') || '')

    if (!email || !password) {
      setError('Please enter both your email and password.')
      return
    }

    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }).toString(),
      })

      const result = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(result.detail || 'Incorrect email or password')
      }

      onLogin({ token: result.access_token, user: result.user })
      navigate('/dashboard')
    } catch (err) {
      setError(friendlyErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
      <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-8 shadow-lg">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Welcome back</p>
        <h2 className="mt-3 text-3xl font-semibold text-slate-900">Log in to MIRROR</h2>
        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <label className="block text-sm text-slate-600">
            Email
            <input name="email" type="email" required className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none ring-0 transition focus:border-violet-500 focus:bg-white" />
          </label>
          <PasswordField label="Password" name="password" autoComplete="current-password" />
          <div className="flex items-center justify-between text-sm">
            <Link to="/forgot-password" className="font-medium text-violet-700">Forgot password?</Link>
          </div>
          {error && <p aria-live="polite" className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <button type="submit" disabled={loading} className="w-full rounded-full bg-slate-900 px-6 py-3 font-medium text-white disabled:opacity-60">
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">Need an account? <Link to="/register" className="font-medium text-violet-700">Create one</Link></p>
      </div>
    </div>
  )
}

function RegisterPage({ onLogin }: { onLogin: (auth: AuthState) => void }) {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') || '').trim()
    const password = String(form.get('password') || '')
    const confirm = String(form.get('password_confirm') || '')

    if (!email || !password || !confirm) {
      setError('Please complete all fields to create your account.')
      return
    }

    if (password !== confirm) {
      setError('Your passwords do not match. Please retype them.')
      return
    }

    setError('')
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          password_confirm: confirm,
          display_name: form.get('display_name'),
        }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'Registration failed')

      const loginResponse = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }).toString(),
      })

      const loginJson = await loginResponse.json().catch(() => ({}))
      if (!loginResponse.ok) throw new Error(loginJson.detail || 'Unable to log in')

      onLogin({ token: loginJson.access_token, user: loginJson.user })
      navigate('/dashboard')
    } catch (err) {
      setError(friendlyErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
      <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-8 shadow-lg">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Start for free</p>
        <h2 className="mt-3 text-3xl font-semibold text-slate-900">Create your MIRROR</h2>
        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <label className="block text-sm text-slate-600">
            Display name
            <input name="display_name" required className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" />
          </label>
          <label className="block text-sm text-slate-600">
            Email
            <input name="email" type="email" required className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" />
          </label>
          <PasswordField label="Password" name="password" autoComplete="new-password" />
          <PasswordField label="Confirm password" name="password_confirm" autoComplete="new-password" />
          {error && <p aria-live="polite" className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          <button type="submit" disabled={loading} className="w-full rounded-full bg-slate-900 px-6 py-3 font-medium text-white disabled:opacity-60">
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}

function Dashboard({ auth }: { auth: AuthState }) {
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)

  useEffect(() => {
    async function load() {
      const [taskData, summaryData] = await Promise.all([
        apiFetch<TaskItem[]>(`/tasks/`, {}, auth.token),
        apiFetch<Summary>(`/analytics/summary`, {}, auth.token),
      ])
      setTasks(taskData)
      setSummary(summaryData)
    }
    load().catch((err) => console.error(err))
  }, [auth.token])

  const pending = tasks.filter((task) => task.status !== 'completed')
  const today = new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

  return (
    <AppShell auth={auth} title="Dashboard">
      <div className="space-y-6">
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm uppercase tracking-[0.2em] text-violet-700">Good morning</p>
          <h2 className="mt-2 text-3xl font-semibold text-slate-900">{auth.user.display_name}</h2>
          <p className="mt-2 text-slate-600">Here is your current personal model for {today}.</p>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          {[
            { label: 'Today\'s schedule', value: `${tasks.filter((task) => task.start_time).length}`, icon: CalendarDays },
            { label: 'Upcoming deadlines', value: `${tasks.filter((task) => task.due_date).length}`, icon: Target },
            { label: 'Tasks remaining', value: `${pending.length}`, icon: Clock3 },
            { label: 'Available time', value: `${summary ? Math.max(0, 8 - pending.length) : 8}h`, icon: UserCircle2 },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-700"><Icon size={18} /></div>
              <div className="text-2xl font-semibold text-slate-900">{value}</div>
              <div className="mt-2 text-sm text-slate-600">{label}</div>
            </div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-xl font-semibold text-slate-900">Today's schedule</h3>
              <Link to="/tasks" className="text-sm font-medium text-violet-700">View all</Link>
            </div>
            <div className="space-y-3">
              {tasks.slice(0, 4).map((task) => (
                <div key={task.id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div>
                    <div className="font-medium text-slate-900">{task.title}</div>
                    <div className="text-xs text-slate-500">{task.priority} · {task.status}</div>
                  </div>
                  <div className="text-right text-xs text-slate-500">{task.estimated_duration} min</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-xl font-semibold text-slate-900">Recent simulations</h3>
            <div className="mt-5 space-y-3">
              <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
                <div className="text-sm font-medium text-violet-700">Postpone task</div>
                <div className="mt-1 text-sm text-slate-600">2 conflicts detected · feasible with trade-offs</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-medium text-slate-900">Add new checkpoint</div>
                <div className="mt-1 text-sm text-slate-600">Healthy workload after moving one meeting</div>
              </div>
            </div>
            <Link to="/simulations" className="mt-5 inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white">Run a What-If Simulation</Link>
          </div>
        </div>
      </div>
    </AppShell>
  )
}

function TasksPage({ auth }: { auth: AuthState }) {
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [error, setError] = useState('')
  const [form, setForm] = useState(defaultTaskForm)

  useEffect(() => {
    loadTasks()
  }, [auth.token])

  async function loadTasks() {
    const data = await apiFetch<TaskItem[]>(`/tasks/`, {}, auth.token)
    setTasks(data)
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    try {
      await apiFetch('/tasks/', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          start_time: form.start_time ? new Date(form.start_time).toISOString() : null,
          due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
        }),
      }, auth.token)
      setForm(defaultTaskForm)
      setError('')
      await loadTasks()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create task')
    }
  }

  async function handleDelete(id: number) {
    await apiFetch(`/tasks/${id}`, { method: 'DELETE' }, auth.token)
    await loadTasks()
  }

  return (
    <AppShell auth={auth} title="Tasks">
      <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <form onSubmit={handleCreate} className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Add task</h3>
          <div className="mt-5 space-y-4">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Task title" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" required />
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" />
            <div className="grid gap-3 md:grid-cols-2">
              <input type="datetime-local" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" />
              <input type="datetime-local" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <option value="not_started">Not started</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
              </select>
              <input type="number" value={form.estimated_duration} onChange={(e) => setForm({ ...form, estimated_duration: Number(e.target.value) })} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" min={15} max={480} />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button type="submit" className="w-full rounded-full bg-slate-900 px-6 py-3 font-medium text-white">Create task</button>
          </div>
        </form>

        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <h3 className="text-xl font-semibold text-slate-900">Task list</h3>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{tasks.length} tasks</span>
          </div>
          <div className="space-y-3">
            {tasks.map((task) => (
              <div key={task.id} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-medium text-slate-900">{task.title}</div>
                  <div className="text-xs text-slate-500">{task.category} · {task.priority} · {task.status}</div>
                </div>
                <div className="flex gap-2">
                  <button type="button" onClick={() => handleDelete(task.id)} className="rounded-full border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-700">Delete</button>
                  <button type="button" onClick={async () => {
                    await apiFetch(`/tasks/${task.id}`, {
                      method: 'PUT',
                      body: JSON.stringify({ status: 'completed' }),
                    }, auth.token)
                    await loadTasks()
                  }} className="rounded-full bg-slate-900 px-3 py-1.5 text-sm text-white">Complete</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  )
}

function CalendarPage({ auth }: { auth: AuthState }) {
  const [tasks, setTasks] = useState<TaskItem[]>([])
  useEffect(() => {
    const start = new Date(); start.setHours(0,0,0,0)
    const end = new Date(); end.setDate(end.getDate() + 7)
    apiFetch<{ tasks: TaskItem[] }>(`/calendar/schedule?start=${start.toISOString()}&end=${end.toISOString()}`, {}, auth.token)
      .then((data) => setTasks(data.tasks || []))
      .catch((err) => console.error(err))
  }, [auth.token])

  return (
    <AppShell auth={auth} title="Calendar">
      <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-xl font-semibold text-slate-900">Weekly timeline</h3>
        <div className="mt-6 space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div>
                <div className="font-medium text-slate-900">{task.title}</div>
                <div className="text-xs text-slate-500">{task.start_time ? new Date(task.start_time).toLocaleString() : 'Flexible'} · {task.priority}</div>
              </div>
              <span className="rounded-full bg-violet-100 px-2 py-1 text-xs font-medium text-violet-700">{task.status}</span>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  )
}

function SimulationPage({ auth }: { auth: AuthState }) {
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [simulation, setSimulation] = useState<any>(null)

  useEffect(() => {
    apiFetch<TaskItem[]>(`/tasks/`, {}, auth.token).then(setTasks).catch(console.error)
  }, [auth.token])

  async function runScenario(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload = {
      task_id: Number(form.get('task_id')),
      scenario_type: String(form.get('scenario_type')),
      new_priority: form.get('new_priority') ? String(form.get('new_priority')) : undefined,
      new_duration: form.get('new_duration') ? Number(form.get('new_duration')) : undefined,
    }
    const data = await apiFetch('/simulations/run', { method: 'POST', body: JSON.stringify(payload) }, auth.token)
    setSimulation(data)
  }

  return (
    <AppShell auth={auth} title="What-If Simulator">
      <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
        <form onSubmit={runScenario} className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Scenario test</h3>
          <div className="mt-5 space-y-4">
            <select name="task_id" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" required>
              {tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}
            </select>
            <select name="scenario_type" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" required>
              <option value="postpone">Postpone</option>
              <option value="skip">Skip</option>
              <option value="move">Move</option>
              <option value="extend">Extend duration</option>
              <option value="priority">Change priority</option>
            </select>
            <input name="new_duration" type="number" min={15} max={480} placeholder="New duration (minutes)" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3" />
            <select name="new_priority" className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <option value="">No priority change</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <button type="submit" className="w-full rounded-full bg-slate-900 px-6 py-3 font-medium text-white">Run simulation</button>
          </div>
        </form>

        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Impact analysis</h3>
          {simulation ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
                <div className="text-sm text-violet-700">Feasibility</div>
                <div className="mt-2 text-xl font-semibold text-slate-900">{simulation.feasibility_result}</div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-500">Workload before</div>
                  <div className="text-2xl font-semibold text-slate-900">{simulation.impact_analysis.workload_before}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-500">Workload after</div>
                  <div className="text-2xl font-semibold text-slate-900">{simulation.impact_analysis.workload_after}</div>
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                {simulation.impact_analysis.explanation}
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-300 p-12 text-center text-slate-500">No simulation yet. Choose an existing task and test a scenario.</div>
          )}
        </div>
      </div>
    </AppShell>
  )
}

function ProfilePage({ auth }: { auth: AuthState }) {
  const [user, setUser] = useState<any>(null)
  const [prefs, setPrefs] = useState<any>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/users/me', {}, auth.token),
      apiFetch('/users/preferences', {}, auth.token),
    ]).then(([userData, prefData]) => {
      setUser(userData)
      setPrefs(prefData)
    }).catch(console.error)
  }, [auth.token])

  async function exportData() {
    const data = await apiFetch('/users/me', {}, auth.token)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'mirror-export.json'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <AppShell auth={auth} title="Profile">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Profile</h3>
          <div className="mt-5 space-y-3 text-sm text-slate-600">
            <div><span className="font-medium text-slate-900">Display name:</span> {user?.display_name}</div>
            <div><span className="font-medium text-slate-900">Email:</span> {user?.email}</div>
            <div><span className="font-medium text-slate-900">Timezone:</span> {user?.time_zone || 'UTC'}</div>
          </div>
          <button type="button" onClick={exportData} className="mt-6 inline-flex rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-medium">Export data</button>
        </div>
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Planning preferences</h3>
          <div className="mt-5 space-y-3 text-sm text-slate-600">
            <div><span className="font-medium text-slate-900">Available hours:</span> {prefs?.available_hours}</div>
            <div><span className="font-medium text-slate-900">Planning style:</span> {prefs?.preferred_planning_style}</div>
            <div><span className="font-medium text-slate-900">Theme:</span> {prefs?.theme}</div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}

function SettingsPage({ auth }: { auth: AuthState }) {
  return (
    <AppShell auth={auth} title="Settings">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Notifications</h3>
          <div className="mt-4 space-y-3 text-sm text-slate-600">
            <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3"><span>Enable browser notifications</span><span className="text-violet-700">Optional</span></div>
            <div className="flex items-center justify-between rounded-2xl bg-slate-50 p-3"><span>Reminder lead time</span><span>15 minutes</span></div>
          </div>
        </div>
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-xl font-semibold text-slate-900">Privacy</h3>
          <button type="button" className="mt-4 rounded-full bg-red-600 px-4 py-2 text-sm font-medium text-white">Delete account</button>
        </div>
      </div>
    </AppShell>
  )
}

function AppShell({ auth, title, children }: { auth: AuthState; title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-stone-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/dashboard" className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">M</div>
              <p className="text-lg font-semibold tracking-[0.2em] text-slate-900">MIRROR</p>
            </Link>
            <span className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 md:inline-flex">{title}</span>
          </div>
          <nav className="hidden items-center gap-6 md:flex">
            <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">Dashboard</Link>
            <Link to="/tasks" className="text-sm text-slate-600 hover:text-slate-900">Tasks</Link>
            <Link to="/calendar" className="text-sm text-slate-600 hover:text-slate-900">Calendar</Link>
            <Link to="/simulations" className="text-sm text-slate-600 hover:text-slate-900">Simulations</Link>
            <Link to="/profile" className="text-sm text-slate-600 hover:text-slate-900">Profile</Link>
          </nav>
          <div className="flex items-center gap-3">
            <button type="button" className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-medium">{auth.user.display_name}</button>
            <button type="button" onClick={() => localStorage.removeItem('mirror_auth')} className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white">Log out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  )
}

export default App
