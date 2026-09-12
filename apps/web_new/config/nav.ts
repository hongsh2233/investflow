/**
 * 하단 네비게이션 — v2 4탭: 투자운세 / 뉴스 / 관심종목 / 대가들의 한마디
 * 데이터: config/nav-items.json
 */
import Article from '@mui/icons-material/Article'
import AutoAwesome from '@mui/icons-material/AutoAwesome'
import Star from '@mui/icons-material/Star'
import FormatQuote from '@mui/icons-material/FormatQuote'
import navData from './nav-items.json'

type IconComponent = typeof Article

interface NavItemData {
  id: string
  label: string
  href: string
  headerTitle: string
  headerSubtitle: string
}

const iconMap: Record<string, IconComponent> = {
  fortune: AutoAwesome,
  news: Article,
  watchlist: Star,
  masters: FormatQuote,
}

export interface NavItem {
  id: string
  label: string
  href: string
  icon: IconComponent
  headerTitle: string
  headerSubtitle: string
}

export const navItems: NavItem[] = (navData as NavItemData[]).map((item) => ({
  ...item,
  icon: iconMap[item.id] ?? AutoAwesome,
}))
