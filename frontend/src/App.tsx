import { Link, Route, Routes } from 'react-router-dom'

import { Dashboard } from './pages/Dashboard'
import { JobAnalysis } from './pages/JobAnalysis'
import { JobComparison } from './pages/JobComparison'
import { MatchResults } from './pages/MatchResults'
import { ResumeOptimization } from './pages/ResumeOptimization'
import { ResumeUpload } from './pages/ResumeUpload'

export function App() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-slate-200 px-6 py-3 flex gap-6 items-center">
        <span className="font-bold text-slate-900">Resume Matcher</span>
        <Link to="/" className="text-sm text-slate-600 hover:text-indigo-600">
          Dashboard
        </Link>
        <Link to="/resume/upload" className="text-sm text-slate-600 hover:text-indigo-600">
          Upload Resume
        </Link>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/resume/upload" element={<ResumeUpload />} />
        <Route path="/jobs/new" element={<JobAnalysis />} />
        <Route path="/matches/new" element={<MatchResults />} />
        <Route path="/jobs/compare" element={<JobComparison />} />
        <Route path="/resume/optimize" element={<ResumeOptimization />} />
      </Routes>
    </div>
  )
}
