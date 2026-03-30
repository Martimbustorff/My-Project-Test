import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, FlatList, StyleSheet,
  TouchableOpacity, ActivityIndicator, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet } from '@/constants/Api';

interface Signal {
  symbol: string;
  timestamp: string;
  action: string;
  confidence: number;
  consensus_score: number;
  recommendation: string;
  direction: string;
  agreement_pct: number;
  technical_score: number;
  sentiment_score: number;
  momentum_score: number;
  fundamental_score: number;
  price: number;
}

interface AnalysisCache {
  key_reasons?: string[];
  key_risks?: string[];
}

type FilterType = 'all' | 'strong' | 'longs' | 'shorts';

const AGENT_ICONS: Record<string, string> = {
  Technical: '🔬',
  Fundamental: '📊',
  Momentum: '📈',
  Sentiment: '📰',
};

const AGENT_SCORE_FIELDS: { name: string; field: keyof Signal }[] = [
  { name: 'Technical',   field: 'technical_score' },
  { name: 'Fundamental', field: 'fundamental_score' },
  { name: 'Momentum',    field: 'momentum_score' },
  { name: 'Sentiment',   field: 'sentiment_score' },
];

function scoreToSignal(score: number): string {
  if (score >= 0.6)  return 'STRONG BUY';
  if (score >= 0.25) return 'BUY';
  if (score > -0.25) return 'HOLD';
  if (score > -0.6)  return 'SELL';
  return 'STRONG SELL';
}

function signalBadgeColor(rec: string): string {
  const u = rec.toUpperCase();
  if (u === 'STRONG BUY') return '#00D4AA';
  if (u === 'BUY')         return '#00A86B';
  if (u === 'HOLD')        return '#FFD700';
  if (u === 'SELL')        return '#FF8C00';
  if (u === 'STRONG SELL') return '#FF4757';
  return Colors.textMuted;
}

function timeAgo(isoDate: string): string {
  const diff = (Date.now() - new Date(isoDate).getTime()) / 1000;
  if (diff < 60)    return `${Math.floor(diff)}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function RecoBadge({ label }: { label: string }) {
  const color = signalBadgeColor(label);
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction === 'LONG';
  const color = isLong ? Colors.green : Colors.red;
  return (
    <View style={[styles.dirBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.dirBadgeText, { color }]}>{direction}</Text>
    </View>
  );
}

function MiniScoreBar({ score }: { score: number }) {
  const abs = Math.abs(score);
  const color = score > 0 ? Colors.green : score < 0 ? Colors.red : Colors.textMuted;
  return (
    <View style={styles.miniBarBg}>
      <View style={[styles.miniBarFill, { width: `${Math.min(abs * 100, 100)}%`, backgroundColor: color }]} />
    </View>
  );
}

interface SignalCardProps {
  item: Signal;
  expanded: boolean;
  onPress: () => void;
  analysisCache: AnalysisCache | null;
}

function SignalCard({ item, expanded, onPress, analysisCache }: SignalCardProps) {
  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.85}>
      {/* Collapsed: Row 1 */}
      <View style={styles.cardRow1}>
        <Text style={styles.symbolText}>{item.symbol}</Text>
        <View style={styles.cardRow1Right}>
          <RecoBadge label={item.recommendation || item.action} />
          <DirectionBadge direction={item.direction || 'LONG'} />
        </View>
      </View>

      {/* Collapsed: Row 2 */}
      <View style={styles.cardRow2}>
        <Text style={styles.metaText}>
          Score: <Text style={{ color: item.consensus_score > 0 ? Colors.green : Colors.red }}>
            {item.consensus_score.toFixed(2)}
          </Text>
        </Text>
        <Text style={styles.metaSep}>·</Text>
        <Text style={styles.metaText}>
          Agreement: <Text style={styles.metaHighlight}>{item.agreement_pct?.toFixed(0) ?? '—'}%</Text>
        </Text>
        <Text style={styles.metaSep}>·</Text>
        <Text style={styles.metaText}>
          ${item.price?.toFixed(2) ?? '—'}
        </Text>
      </View>

      {/* Collapsed: Row 3 — timestamp */}
      <Text style={styles.timestampText}>{timeAgo(item.timestamp)}</Text>

      {/* Expanded content */}
      {expanded && (
        <View style={styles.expandedSection}>
          <View style={styles.expandDivider} />

          {/* Agent votes */}
          <Text style={styles.sectionLabel}>Agent Votes</Text>
          {AGENT_SCORE_FIELDS.map(agent => {
            const score = item[agent.field] as number;
            const signal = scoreToSignal(score);
            const icon = AGENT_ICONS[agent.name] ?? '';
            const color = signalBadgeColor(signal);
            return (
              <View key={agent.name} style={styles.agentRow}>
                <Text style={styles.agentIcon}>{icon}</Text>
                <Text style={styles.agentName}>{agent.name}</Text>
                <View style={styles.agentBarContainer}>
                  <MiniScoreBar score={score} />
                </View>
                <View style={[styles.agentBadge, { backgroundColor: color + '22', borderColor: color }]}>
                  <Text style={[styles.agentBadgeText, { color }]}>{signal}</Text>
                </View>
                <Text style={[styles.agentScore, { color: score > 0 ? Colors.green : score < 0 ? Colors.red : Colors.textMuted }]}>
                  {score >= 0 ? '+' : ''}{score.toFixed(2)}
                </Text>
              </View>
            );
          })}

          {/* Bull case */}
          {analysisCache?.key_reasons && analysisCache.key_reasons.length > 0 && (
            <View style={styles.caseSection}>
              <Text style={styles.caseSectionTitle}>🐂 Bull Case</Text>
              {analysisCache.key_reasons.map((r, i) => (
                <Text key={i} style={styles.bulletText}>• {r}</Text>
              ))}
            </View>
          )}

          {/* Bear case */}
          {analysisCache?.key_risks && analysisCache.key_risks.length > 0 && (
            <View style={styles.caseSection}>
              <Text style={styles.caseSectionTitle}>🐻 Bear Case</Text>
              {analysisCache.key_risks.map((r, i) => (
                <Text key={i} style={styles.bulletText}>• {r}</Text>
              ))}
            </View>
          )}
        </View>
      )}
    </TouchableOpacity>
  );
}

export default function SignalsScreen() {
  const [signals, setSignals]         = useState<Signal[]>([]);
  const [loading, setLoading]         = useState(true);
  const [filter, setFilter]           = useState<FilterType>('all');
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [analysisBySymbol, setAnalysisBySymbol] = useState<Record<string, AnalysisCache>>({});
  const [error, setError]             = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await apiGet<Signal[]>('/api/signals/latest?limit=50');
      setSignals(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const i = setInterval(load, 30_000);
    return () => clearInterval(i);
  }, [load]);

  const handleCardPress = useCallback(async (symbol: string) => {
    if (expandedSymbol === symbol) {
      setExpandedSymbol(null);
      return;
    }
    setExpandedSymbol(symbol);
    // Lazy-load analysis cache if not already fetched
    if (!analysisBySymbol[symbol]) {
      try {
        const data = await apiGet<AnalysisCache>(`/api/analysis/${symbol}`);
        setAnalysisBySymbol(prev => ({ ...prev, [symbol]: data }));
      } catch {
        setAnalysisBySymbol(prev => ({ ...prev, [symbol]: {} }));
      }
    }
  }, [expandedSymbol, analysisBySymbol]);

  const displayed = signals.filter(s => {
    if (filter === 'strong') return Math.abs(s.consensus_score) > 0.5;
    if (filter === 'longs')  return s.direction === 'LONG';
    if (filter === 'shorts') return s.direction === 'SHORT';
    return true;
  });

  const FILTERS: { key: FilterType; label: string }[] = [
    { key: 'all',    label: 'All' },
    { key: 'strong', label: 'Strong' },
    { key: 'longs',  label: 'Longs' },
    { key: 'shorts', label: 'Shorts' },
  ];

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading signals...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Signals</Text>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>
            {error === 'UNAUTHORIZED' ? 'Session expired' : 'Could not reach API server'}
          </Text>
        </View>
      )}

      {/* Filter row */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filterRow}
      >
        {FILTERS.map(f => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterBtn, filter === f.key && styles.filterBtnActive]}
            onPress={() => setFilter(f.key)}
          >
            <Text style={[styles.filterText, filter === f.key && styles.filterTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <FlatList
        data={displayed}
        keyExtractor={item => item.symbol + item.timestamp}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No signals match this filter.</Text>
          </View>
        }
        renderItem={({ item }) => (
          <SignalCard
            item={item}
            expanded={expandedSymbol === item.symbol}
            onPress={() => handleCardPress(item.symbol)}
            analysisCache={analysisBySymbol[item.symbol] ?? null}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textSecondary, marginTop: 12 },

  header: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 4 },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text },

  errorBanner: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#3D1010',
    borderRadius: 8,
    padding: 12,
  },
  errorText: { color: Colors.red, fontSize: 13 },

  filterRow: { paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  filterBtn: {
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  filterBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterText: { fontSize: 13, color: Colors.textSecondary, fontWeight: '600' },
  filterTextActive: { color: '#fff' },

  listContent: { paddingHorizontal: 16, paddingBottom: 40 },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', lineHeight: 22 },

  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardRow1: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardRow1Right: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  symbolText: { fontSize: 18, fontWeight: '800', color: Colors.text },

  badge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  badgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  dirBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1 },
  dirBadgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },

  cardRow2: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  metaText: { fontSize: 12, color: Colors.textSecondary },
  metaSep: { fontSize: 12, color: Colors.textMuted },
  metaHighlight: { color: Colors.text, fontWeight: '600' },

  timestampText: { fontSize: 11, color: Colors.textMuted },

  expandedSection: { marginTop: 4 },
  expandDivider: { height: 1, backgroundColor: Colors.border, marginVertical: 12 },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 10,
  },

  agentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 6,
  },
  agentIcon: { fontSize: 14, width: 20 },
  agentName: { fontSize: 12, color: Colors.textSecondary, width: 80 },
  agentBarContainer: { flex: 1 },
  miniBarBg: {
    height: 5,
    backgroundColor: Colors.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  miniBarFill: { height: 5, borderRadius: 3 },
  agentBadge: {
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderWidth: 1,
    minWidth: 70,
    alignItems: 'center',
  },
  agentBadgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.3 },
  agentScore: { fontSize: 11, fontWeight: '600', width: 38, textAlign: 'right' },

  caseSection: { marginTop: 12 },
  caseSectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: 6,
  },
  bulletText: {
    fontSize: 12,
    color: Colors.textSecondary,
    lineHeight: 18,
    marginBottom: 3,
  },
});
