/**
 * CheckUp Direct — Professional Trading Platform
 * Design tokens for dark trading UI.
 */

export const Colors = {
  // ── Brand ──────────────────────────────────────────────
  primary:        '#0057A6',
  primaryLight:   '#1A6FBF',
  primaryDark:    '#003D7A',
  primaryGlow:    'rgba(0,87,166,0.20)',

  // ── Backgrounds ────────────────────────────────────────
  background:     '#080D1A',   // deepest
  surface:        '#0E1629',   // cards
  surfaceAlt:     '#142035',   // input fields, hover
  surfaceHover:   '#1A2A45',   // hover state
  overlay:        'rgba(8,13,26,0.92)',

  // ── Borders ────────────────────────────────────────────
  border:         '#1C2E47',
  borderLight:    '#243A58',
  borderFocus:    '#0057A6',

  // ── Text ───────────────────────────────────────────────
  text:           '#ECF2FF',
  textSecondary:  '#7A90AD',
  textMuted:      '#3D5068',
  textInverse:    '#080D1A',

  // ── Financial signals ──────────────────────────────────
  green:          '#00D4AA',
  greenDim:       'rgba(0,212,170,0.15)',
  greenBright:    '#00FFD1',
  red:            '#FF4757',
  redDim:         'rgba(255,71,87,0.15)',
  yellow:         '#FFD93D',
  yellowDim:      'rgba(255,217,61,0.15)',
  orange:         '#FF8C42',
  blue:           '#4B9EFF',
  blueDim:        'rgba(75,158,255,0.15)',
  purple:         '#A855F7',
  purpleDim:      'rgba(168,85,247,0.15)',

  // ── Recommendations ────────────────────────────────────
  strongBuy:      '#00FFD1',
  buy:            '#00D4AA',
  hold:           '#FFD93D',
  sell:           '#FF8C42',
  strongSell:     '#FF4757',

  // ── Tab / Nav ──────────────────────────────────────────
  sidebar:        '#0A1220',
  tabBar:         '#0A1220',
  tabIconDefault: '#3D5068',
  tabIconSelected:'#0057A6',

  // ── Legacy (keep for existing components) ──────────────
  light: {
    text: '#ECF2FF', background: '#080D1A', tint: '#0057A6',
    icon: '#7A90AD', tabIconDefault: '#3D5068', tabIconSelected: '#0057A6',
  },
  dark: {
    text: '#ECF2FF', background: '#080D1A', tint: '#0057A6',
    icon: '#7A90AD', tabIconDefault: '#3D5068', tabIconSelected: '#0057A6',
  },
};

// Recommendation → color map (used everywhere)
export function recColor(rec?: string): string {
  if (!rec) return Colors.textMuted;
  const u = rec.toUpperCase().replace(' ', '_');
  if (u === 'STRONG_BUY')  return Colors.strongBuy;
  if (u === 'BUY')         return Colors.buy;
  if (u === 'HOLD')        return Colors.hold;
  if (u === 'SELL')        return Colors.sell;
  if (u === 'STRONG_SELL') return Colors.strongSell;
  return Colors.textMuted;
}
