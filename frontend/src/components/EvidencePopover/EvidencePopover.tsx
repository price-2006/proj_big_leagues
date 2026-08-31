import { useState } from 'react'

// "click a claim -> see the exact resume/JD span it's grounded in"
// (docs/ARCHITECTURE.md §11). An inline expand/collapse disclosure
// rather than an absolutely-positioned floating popover — same
// click-to-reveal interaction, without the overflow/z-index fragility a
// floating popover would add for one portfolio-scope component.
interface EvidencePopoverProps {
  text: string
  evidenceText: string | null
  isInference: boolean
}

export function EvidencePopover({ text, evidenceText, isInference }: EvidencePopoverProps) {
  const [open, setOpen] = useState(false)

  return (
    <div>
      <p className="text-sm text-slate-700">
        {text}{' '}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="text-xs font-medium text-indigo-500 hover:text-indigo-700"
        >
          {isInference && !evidenceText ? '(inference)' : '(show evidence)'}
        </button>
      </p>
      {open && (
        <div className="mt-1 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          {evidenceText ? (
            <>
              <span className="text-slate-400">From the resume/job description: </span>"{evidenceText}"
            </>
          ) : (
            'This is a reasonable inference, not a direct quote from the resume or job description.'
          )}
        </div>
      )}
    </div>
  )
}
