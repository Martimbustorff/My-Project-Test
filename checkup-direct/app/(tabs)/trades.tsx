// Market scanner — shows top BUY and SHORT opportunities from multi-agent consensus
import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, FlatList, StyleSheet,
  ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet, apiPost } from '@/constants/Api';

interface Opportunity {
  symbol: string;
  rank?: number;
  recommendation?: string;
  consensus_score: number;
  confidence?: number;
  agreement_pct?: number;
  direction?: string;
  key_reasons?: string[];
  agents_agree?: number;
}

interface ScannerResult {
  top_longs: Opportunity[];
  top_shorts: Opportunity[];
  last_scan: string | null;
  scanning: boolean;
  progress?: number;
  total?: number;
  symbols_scanned?: number;
}

type TabType = 'longs' | 'shorts';

function signalBadgeColor(rec?: string): string {
  if (!rec) return Colors.textMuted;
  const u = rec.toUpperCase();
  if (u === 'STRONG BUY') return '#00D4AA';
  if (u === 'BUY') return '#00A86B';
  if (u === 'HOLD') return '#FFD700';
  if (u === 'SELL') return '#FF8C00';
  if (u === 'STRONG SELL') return '#FF4757';
  return Colors.textMuted;
}

const ScoreBar = ({ score }: { score: number }) => {
  const absScore = Math.abs(score);
  const color = score > 0 ? Colors.green : Colors.red;
  return (
    <View style={{ height: 6, backgroundColor: Colors.border, borderRadius: 3, width: '100%' }}>
      <View style={{ height: 6, width: `${Math.min(absScore * 100, 100)}%`, backgroundColor: color, borderRadius: 3 }} />
    </View>
  );
};

function SignalBadge({ label }: { label?: string }) {
  if (!label) return null;
  const color = signalBadgeColor(label);
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

function OpportunityCard({ item, rank }: { item: Opportunity; rank: number }) {
  const direction = item.direction ?? (item.consensus_score > 0 ? 'LONG' : 'SHORT');
  const agentsAgree = item.agents_agree ?? 0;
  const agreementPct = item.agreement_pct != null ? item.agreement_pct.toFixed(0) : '—';
  const keyReason = item.key_reasons && item.key_reasons.length > 0 ? item.key_reasons[0] : null;

  return (
    <View style={styles.card}>
      {/* Row 1: Rank, Symbol, Badge */}
      <View style={styles.cardRow1}>
        <View style={styles.cardRow1Left}>
          <Text style={styles.rankText}>#{rank}</Text>
          <Text style={styles.symbolText}>{item.symbol}</Text>
        </View>
        <SignalBadge label={item.recommendation} />
      </View>

      {/* Row 2: Score bar */}
      <View style={styles.scoreBarContainer}>
        <ScoreBar score={item.consensus_score} />
      </View>
      <View style={styles.scoreRow}>
        <Text style={styles.scoreText}>
          Score: <Text style={{ color: (item.consensus_score ?? 0) > 0 ? Colors.green : Colors.red }}>
            {(item.consensus_score ?? 0).toFixed(2)}
          </Text>
        </Text>
        <Text style={styles.scoreText}>
          Confidence: <Text style={styles.scoreHighlight}>{agreementPct}%</Text>
        </Text>
      </View>

      {/* Row 3: Agreement and direction */}
      <View style={styles.cardRow3}>
        <Text style={styles.metaText}>Agreement: {agentsAgree}/4 agents</Text>
        <Text style={styles.metaSep}>·</Text>
        <Text style={[styles.directionText, { color: direction === 'LONG' ? Colors.green : Colors.red }]}>
          {direction}
        </Text>
      </View>

      {/* Row 4: Key reason */}
      {keyReason && (
        <Text style={styles.reasonText} numberOfLines={1}>{keyReason}</Text>
      )}
    </View>
  );
}

function timeAgo(isoDate: string | null): string {
  if (!isoDate) return 'Never';
  const diff = (Date.now() - new Date(isoDate).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function ScannerScreen() {
  const [data, setData] = useState<ScannerResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('longs');
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchResults = useCallback(async () => {
    try {
      setError(null);
      const result = await apiGet<ScannerResult>('/api/scanner/results');
      setData(result);
      setScanning(result.scanning ?? false);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const startPolling = useCallback((isScanning: boolean) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    const interval = isScanning ? 3000 : 60000;
    intervalRef.current = setInterval(fetchResults, interval);
  }, [fetchResults]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  useEffect(() => {
    startPolling(scanning);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [scanning, startPolling]);

  const handleScanNow = async () => {
    try {
      setScanning(true);
      await apiPost('/api/scanner/run', {});
      startPolling(true);
      await fetchResults();
    } catch (e: any) {
      setError(e.message);
      setScanning(false);
    }
  };

  const displayed = activeTab === 'longs'
    ? (data?.top_longs ?? []).map((item, i) => ({ ...item, rank: i + 1 }))
    : (data?.top_shorts ?? []).map((item, i) => ({ ...item, rank: i + 1 }));

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading scanner...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Market Scanner</Text>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>
            {error === 'UNAUTHORIZED' ? 'Session expired' : 'Could not reach API server'}
          </Text>
        </View>
      )}

      {/* Status row */}
      <View style={styles.statusRow}>
        <Text style={styles.statusText}>
          Last scan: {timeAgo(data?.last_scan ?? null)}
        </Text>
        <TouchableOpacity
          style={[styles.scanBtn, scanning && { opacity: 0.7 }]}
          onPress={handleScanNow}
          disabled={scanning}
        >
          <Text style={styles.scanBtnText}>🔭 Scan Now</Text>
        </TouchableOpacity>
      </View>

      {/* Tab buttons */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tabBtn, activeTab === 'longs' && styles.tabBtnActiveLong]}
          onPress={() => setActiveTab('longs')}
        >
          <Text style={[styles.tabBtnText, activeTab === 'longs' && { color: Colors.green }]}>
            ▲ TOP LONGS
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabBtn, activeTab === 'shorts' && styles.tabBtnActiveShort]}
          onPress={() => setActiveTab('shorts')}
        >
          <Text style={[styles.tabBtnText, activeTab === 'shorts' && { color: Colors.red }]}>
            ▼ TOP SHORTS
          </Text>
        </TouchableOpacity>
      </View>

      {/* Scanning state */}
      {scanning && (
        <View style={styles.scanningBanner}>
          <ActivityIndicator size="small" color={Colors.primary} />
          <Text style={styles.scanningText}>Scanning market...</Text>
          {data?.symbols_scanned != null && data?.total != null && (
            <Text style={styles.scanningProgress}>
              {data.symbols_scanned} / {data.total}
            </Text>
          )}
        </View>
      )}

      <FlatList
        data={displayed}
        keyExtractor={item => item.symbol}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>
              No scan data yet. Tap Scan Now to analyze the market.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <OpportunityCard item={item} rank={item.rank ?? 1} />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textSecondary, marginTop: 12 },

  header: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text },

  errorBanner: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#3D1010',
    borderRadius: 8,
    padding: 12,
  },
  errorText: { color: Colors.red, fontSize: 13 },

  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  statusText: { fontSize: 13, color: Colors.textSecondary },
  scanBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  scanBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  tabRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginBottom: 12,
    gap: 8,
  },
  tabBtn: {
    flex: 1,
    height: 40,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabBtnActiveLong: {
    borderColor: Colors.green,
    backgroundColor: Colors.green + '18',
  },
  tabBtnActiveShort: {
    borderColor: Colors.red,
    backgroundColor: Colors.red + '18',
  },
  tabBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.textSecondary,
    letterSpacing: 0.5,
  },

  scanningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 10,
    backgroundColor: Colors.surface,
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  scanningText: { fontSize: 13, color: Colors.textSecondary, flex: 1 },
  scanningProgress: { fontSize: 12, color: Colors.textMuted },

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
    marginBottom: 10,
  },
  cardRow1Left: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  rankText: { fontSize: 12, color: Colors.textMuted, fontWeight: '600', width: 28 },
  symbolText: { fontSize: 18, fontWeight: '800', color: Colors.text },

  badge: {
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
  },
  badgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  scoreBarContainer: { marginBottom: 6 },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  scoreText: { fontSize: 12, color: Colors.textSecondary },
  scoreHighlight: { color: Colors.text, fontWeight: '600' },

  cardRow3: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  metaText: { fontSize: 12, color: Colors.textSecondary },
  metaSep: { fontSize: 12, color: Colors.textMuted },
  directionText: { fontSize: 12, fontWeight: '700' },

  reasonText: {
    fontSize: 12,
    color: Colors.textMuted,
    marginTop: 4,
    fontStyle: 'italic',
  },
});
