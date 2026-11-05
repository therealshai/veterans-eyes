import { useRoute } from '@/lib/router'
import Home from '@/screens/Home'
import NewGuide from '@/screens/NewGuide'
import Review from '@/screens/Review'
import Coach from '@/screens/Coach'
import Summary from '@/screens/Summary'

// Each screen owns its data; the URL hash decides which one shows.
export default function App() {
  const route = useRoute()
  switch (route.name) {
    case 'new': return <NewGuide />
    case 'review': return <Review id={route.id} key={route.id} />
    case 'coach': return <Coach id={route.id} key={route.id} />
    case 'summary': return <Summary id={route.id} key={route.id} />
    default: return <Home />
  }
}
