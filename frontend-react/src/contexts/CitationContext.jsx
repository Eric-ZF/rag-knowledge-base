import { createContext, useContext, useState } from 'react'

const CitationContext = createContext(null)

export function CitationProvider({ children }) {
  const [citations, setCitations] = useState([])

  const addCitation = (paper) => {
    if (citations.some(c => c.paper_id === paper.paper_id)) return
    setCitations(prev => [...prev, paper])
  }

  const removeCitation = (paperId) => {
    setCitations(prev => prev.filter(c => c.paper_id !== paperId))
  }

  const clearCitations = () => setCitations([])

  const getCitationPrefix = () => {
    return citations.map((c, i) => {
      const n = i + 1
      const authorPart = c.authors ? ` (${c.authors}${c.year ? ', ' + c.year : ''})` : ''
      return `> [${n}] ${c.title}${authorPart}`
    }).join('\n')
  }

  return (
    <CitationContext.Provider value={{ citations, addCitation, removeCitation, clearCitations, getCitationPrefix }}>
      {children}
    </CitationContext.Provider>
  )
}

export const useCitation = () => useContext(CitationContext)
