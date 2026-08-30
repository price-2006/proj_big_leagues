import { useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'

import { useUploadResume } from '../api/hooks/useResume'
import { useSession } from '../context/SessionContext'

export function ResumeUpload() {
  const [isDragging, setIsDragging] = useState(false)
  const upload = useUploadResume()
  const { addResume } = useSession()

  const handleFile = (file: File) => {
    upload.mutate(file, {
      onSuccess: (resume) => {
        if (!resume) return
        addResume({
          id: resume.id,
          name: resume.parsed_profile.contact.name ?? null,
          filename: resume.original_filename,
        })
      },
    })
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Upload your resume</h1>
      <p className="text-slate-500 mb-6">PDF or DOCX. We'll extract your skills, experience, and education.</p>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={`rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
          isDragging ? 'border-indigo-400 bg-indigo-50' : 'border-slate-300 bg-slate-50'
        }`}
      >
        <p className="text-slate-600 mb-3">Drag and drop your resume here, or</p>
        <label className="inline-block cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700">
          Choose file
          <input
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFile(file)
            }}
          />
        </label>
      </div>

      {upload.isPending && <p className="mt-4 text-slate-500">Parsing resume…</p>}

      {upload.isError && (
        <p className="mt-4 rounded-md bg-rose-50 px-4 py-3 text-rose-700">
          {upload.error instanceof Error ? upload.error.message : 'Could not parse that file. Try a PDF or DOCX.'}
        </p>
      )}

      {upload.isSuccess && upload.data && (
        <div className="mt-6 rounded-lg border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Parsed profile</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm mb-4">
            <dt className="text-slate-500">Name</dt>
            <dd className="text-slate-900">{upload.data.parsed_profile.contact.name ?? '—'}</dd>
            <dt className="text-slate-500">Email</dt>
            <dd className="text-slate-900">{upload.data.parsed_profile.contact.email ?? '—'}</dd>
          </dl>
          <h3 className="text-sm font-semibold text-slate-600 mb-2">Skills</h3>
          <div className="flex flex-wrap gap-2 mb-4">
            {upload.data.parsed_profile.skills.map((skill) => (
              <span key={skill} className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                {skill}
              </span>
            ))}
          </div>
          <Link
            to={`/jobs/new?resumeId=${upload.data.id}`}
            className="inline-block rounded-md bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700"
          >
            Continue to job analysis
          </Link>
        </div>
      )}
    </div>
  )
}
