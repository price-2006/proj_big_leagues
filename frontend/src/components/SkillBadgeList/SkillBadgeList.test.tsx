import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { SkillBreakdown } from '../../types/models'
import { SkillBadgeList } from './SkillBadgeList'

describe('SkillBadgeList', () => {
  it('renders matched and missing skills for both required and preferred groups', () => {
    const breakdown: SkillBreakdown = {
      matched_required: ['Python', 'PostgreSQL'],
      missing_required: ['Kubernetes'],
      matched_preferred: ['Docker'],
      missing_preferred: ['Terraform'],
    }
    render(<SkillBadgeList breakdown={breakdown} />)

    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
    expect(screen.getByText('Kubernetes')).toBeInTheDocument()
    expect(screen.getByText('Docker')).toBeInTheDocument()
    expect(screen.getByText('Terraform')).toBeInTheDocument()
    expect(screen.getByText('Required skills')).toBeInTheDocument()
    expect(screen.getByText('Preferred skills')).toBeInTheDocument()
  })

  it('omits a group heading entirely when it has no matched or missing skills', () => {
    const breakdown: SkillBreakdown = {
      matched_required: ['Python'],
      missing_required: [],
      matched_preferred: [],
      missing_preferred: [],
    }
    render(<SkillBadgeList breakdown={breakdown} />)
    expect(screen.getByText('Required skills')).toBeInTheDocument()
    expect(screen.queryByText('Preferred skills')).not.toBeInTheDocument()
  })
})
