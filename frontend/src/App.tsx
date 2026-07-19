import { useEffect, useState } from 'react'
import { HomeScreen } from './components/HomeScreen'
import { ProjectView } from './components/ProjectView'
import { AnnotationEditor } from './components/AnnotationEditor'

// Hash routes: #/ | #/p/<project> | #/p/<project>/edit/<filename>
interface Route {
  page: 'home' | 'project' | 'edit'
  project?: string
  filename?: string
}

function parseHash(): Route {
  const parts = window.location.hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent)
  if (parts[0] === 'p' && parts[1]) {
    if (parts[2] === 'edit' && parts[3]) {
      return { page: 'edit', project: parts[1], filename: parts.slice(3).join('/') }
    }
    return { page: 'project', project: parts[1] }
  }
  return { page: 'home' }
}

export function navigate(path: string) {
  window.location.hash = path
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseHash)

  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (route.page === 'edit' && route.project && route.filename) {
    return (
      <AnnotationEditor
        key={route.project}
        project={route.project}
        filename={route.filename}
      />
    )
  }
  if (route.page === 'project' && route.project) {
    return <ProjectView key={route.project} project={route.project} />
  }
  return <HomeScreen />
}
