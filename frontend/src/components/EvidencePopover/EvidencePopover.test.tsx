import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { EvidencePopover } from './EvidencePopover'

describe('EvidencePopover', () => {
  it('does not show the evidence text until clicked', () => {
    render(<EvidencePopover text="Strong Go experience" evidenceText="Built backend services in Go" isInference={false} />)
    expect(screen.getByText('Strong Go experience')).toBeInTheDocument()
    expect(screen.queryByText(/Built backend services in Go/)).not.toBeInTheDocument()
  })

  it('reveals the resolved evidence text on click', () => {
    render(<EvidencePopover text="Strong Go experience" evidenceText="Built backend services in Go" isInference={false} />)
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/Built backend services in Go/)).toBeInTheDocument()
  })

  it('shows an inference note instead of a quote when there is no evidence text', () => {
    render(<EvidencePopover text="Likely comfortable with cloud infra" evidenceText={null} isInference={true} />)
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/reasonable inference, not a direct quote/)).toBeInTheDocument()
  })
})
