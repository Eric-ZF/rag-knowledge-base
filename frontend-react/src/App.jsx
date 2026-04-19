import { AuthProvider, useAuth } from './contexts/AuthContext.jsx'
import { ToastProvider } from './contexts/ToastContext.jsx'
import { CitationProvider } from './contexts/CitationContext.jsx'
import AuthScreen from './components/AuthScreen.jsx'
import MainLayout from './components/AppLayout.jsx'

function AppInner() {
  const { token } = useAuth()
  return token ? <MainLayout /> : <AuthScreen />
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <CitationProvider>
          <AppInner />
        </CitationProvider>
      </ToastProvider>
    </AuthProvider>
  )
}
