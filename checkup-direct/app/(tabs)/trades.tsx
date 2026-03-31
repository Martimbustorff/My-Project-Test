// Market Scanner — trading terminal with multi-agent consensus
import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View, Text, FlatList, StyleSheet,
  ActivityIndicator, TouchableOpacity,
  Animated, useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, recColor } from '@/constants/Colors';
import { MarketBadge } from '@/components/MarketBadge';
import { useToast } from '@/components/Toast';
import { apiGet, apiPost } from '@/constants/Api';

// ─── Types ────────────────────────────────────────────────────────────────────

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
  price?: number;
  change_pct?: number;
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
type SortKey = 'score' | 'confidence' | 'change';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(isoDate: string | null): string {
  if (!isoDate) return 'Never';
  const diff = (Date.now() - new Date(isoDate).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

// ─── Signal Badge ─────────────────────────────────────────────────────────────

function SignalBadge({ label }: { label?: string }) {
  if (!label) return null;
  const color = recColor(label);
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label.toUpperCase()}</Text>
    </View>
  );
}

// ─── Score Bar ────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const absScore = Math.abs(score ?? 0);
  const color = (score ?? 0) > 0 ? Colors.green : Colors.red;
  return (
    <View style={styles.scoreBarTrack}>
      <View
        style={[
          styles.scoreBarFill,
          { width: `${Math.min(absScore * 100, 100)}%` as any, backgroundColor: color },
        ]}
      />
    </View>
  );
}

// ─── Opportunity Card ─────────────────────────────────────────────────────────

function OpportunityCard({ item, rank }: { item: Opportunity; rank: number }) {
  const direction = item.direction ?? ((item.consensus_score ?? 0) > 0 ? 'LONG' : 'SHORT');
  const agentsAgree = item.agents_agree ?? 0;
  const keyReason = item.key_reasons && item.key_reasons.length > 0 ? item.key_reasons[0] : null;
  const changePct = item.change_pct ?? 0;
  const price = item.price ?? 0;
  const confidence = item.confidence ?? 0;
  const score = item.consensus_score ?? 0;

  return (
    <TouchableOpacity style={styles.card} activeOpacity={0.85}>
      {/* Header: rank + symbol + badge */}
      <View style={styles.cardHeader}>
        <Text style={styles.rankText}>#{rank}</Text>
        <Text style={styles.symbolText}>{item.symbol}</Text>
        <View style={{ flex: 1 }} />
        <SignalBadge label={item.recommendation} />
      </View>

      {/* Score bar */}
      <ScoreBar score={score} />

      {/* Price + change + score */}
      <View style={styles.priceRow}>
        {price > 0 ? (
          <Text style={styles.priceText}>${price.toFixed(2)}</Text>
        ) : null}
        {price > 0 && (
          <Text style={[styles.changeText, { color: changePct >= 0 ? Colors.green : Colors.red }]}>
            {changePct >= 0 ? '▲' : '▼'} {Math.abs(changePct).toFixed(2)}%
          </Text>
        )}
        <View style={{ flex: 1 }} />
        <Text style={styles.scoreLabel}>
          Score:{' '}
          <Text style={{ color: score > 0 ? Colors.green : Colors.red, fontWeight: '700' }}>
            {score >= 0 ? '+' : ''}{score.toFixed(2)}
          </Text>
        </Text>
      </View>

      {/* Agents row */}
      <View style={styles.agentRow}>
        <View style={[styles.agentBadge, { backgroundColor: Colors.blueDim, borderColor: Colors.blue + '44' }]}>
          <Text style={[styles.agentBadgeText, { color: Colors.blue }]}>
            {agentsAgree}/5 agents
          </Text>
        </View>
        <View style={[styles.agentBadge, { backgroundColor: Colors.purpleDim, borderColor: Colors.purple + '44' }]}>
          <Text style={[styles.agentBadgeText, { color: Colors.purple }]}>
            {(confidence * 100).toFixed(0)}% conf
          </Text>
        </View>
        <View style={{ flex: 1 }} />
        <Text style={[styles.dirText, { color: direction === 'LONG' ? Colors.green : Colors.red }]}>
          {direction === 'LONG' ? '▲' : '▼'} {direction}
        </Text>
      </View>

      {/* Key reason */}
      {keyReason && (
        <Text style={styles.reasonText} numberOfLines={1}>
          {keyReason}
        </Text>
      )}
    </TouchableOpacity>
  );
}

// ─── Scanning Progress Bar ────────────────────────────────────────────────────

function ScanProgressBar({ progress, total }: { progress: number; total: number }) {
  const anim = useRef(new Animated.Value(0)).current;
  const pct = total > 0 ? progress / total : 0;

  useEffect(() => {
    Animated.timing(anim, { toValue: pct, duration: 400, useNativeDriver: false }).start();
  }, [pct]);

  return (
    <View style={styles.progressTrack}>
      <Animated.View
        style={[
          styles.progressFill,
          { width: anim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) },
        ]}
      />
    </View>
  );
}

// ─── Stats Strip ──────────────────────────────────────────────────────────────

function StatsStrip({
  data,
  lastScan,
}: {
  data: ScannerResult | null;
  lastScan: string | null;
}) {
  const totalScanned = data?.symbols_scanned ?? data?.total ?? 0;
  const longCount = data?.top_longs?.length ?? 0;
  const shortCount = data?.top_shorts?.length ?? 0;

  return (
    <View style={styles.statsStrip}>
      <Text style={styles.stripItem}>
        <Text style={styles.stripValue}>{totalScanned}</Text>
        <Text style={styles.stripLabel}> scanned</Text>
      </Text>
      <Text style={styles.stripSep}>|</Text>
      <Text style={styles.stripItem}>
        <Text style={[styles.stripValue, { color: Colors.green }]}>{longCount}</Text>
        <Text style={styles.stripLabel}> longs</Text>
      </Text>
      <Text style={styles.stripSep}>|</Text>
      <Text style={styles.stripItem}>
        <Text style={[styles.stripValue, { color: Colors.red }]}>{shortCount}</Text>
        <Text style={styles.stripLabel}> shorts</Text>
      </Text>
      <Text style={styles.stripSep}>|</Text>
      <Text style={styles.stripItem}>
        <Text style={styles.stripLabel}>Updated: </Text>
        <Text style={styles.stripValue}>{timeAgo(lastScan)}</Text>
      </Text>
    </View>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────

export default function ScannerScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;
  const toast = useToast();

  const [data, setData]           = useState<ScannerResult | null>(null);
  const [loading, setLoading]     = useState(true);
  const [scanning, setScanning]   = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('longs');
  const [sortKey, setSortKey]     = useState<SortKey>('score');
  const [error, setError]         = useState<string | null>(null);
  const [countdown, setCountdown] = useState(1800); // 30 min in seconds

  const intervalRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoScanRef     = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scanPulse       = useRef(new Animated.Value(1)).current;

  // Pulsing animation for scan button
  useEffect(() => {
    if (scanning) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(scanPulse, { toValue: 0.5, duration: 600, useNativeDriver: true }),
          Animated.timing(scanPulse, { toValue: 1, duration: 600, useNativeDriver: true }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    } else {
      scanPulse.setValue(1);
    }
  }, [scanning]);

  const fetchResults = useCallback(async () => {
    try {
      setError(null);
      const result = await apiGet<ScannerResult>('/api/scanner/results');
      setData(result);
      const isCurrentlyScanning = result.scanning ?? false;
      setScanning(isCurrentlyScanning);
      return isCurrentlyScanning;
    } catch (e: any) {
      setError(e.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const startPolling = useCallback((isScanning: boolean) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    const interval = isScanning ? 3000 : 60000;
    intervalRef.current = setInterval(fetchResults, interval);
  }, [fetchResults]);

  // Countdown timer
  const startCountdown = useCallback(() => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    setCountdown(1800);
    countdownRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          if (countdownRef.current) clearInterval(countdownRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  // Auto-scan after 30 minutes
  useEffect(() => {
    if (autoScanRef.current) clearTimeout(autoScanRef.current);
    autoScanRef.current = setTimeout(() => {
      handleScanNow();
    }, 30 * 60 * 1000);
    return () => {
      if (autoScanRef.current) clearTimeout(autoScanRef.current);
    };
  }, [data?.last_scan]);

  useEffect(() => {
    fetchResults().then(isScanning => {
      startPolling(isScanning);
      if (!isScanning) startCountdown();
    });
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  useEffect(() => {
    startPolling(scanning);
    if (!scanning) startCountdown();
  }, [scanning]);

  const handleScanNow = async () => {
    try {
      setScanning(true);
      if (countdownRef.current) clearInterval(countdownRef.current);
      await apiPost('/api/scanner/run', {});
      startPolling(true);
      await fetchResults();
      toast.show({ message: 'Market scan started.', type: 'info' });
    } catch (e: any) {
      setError(e.message);
      setScanning(false);
      toast.show({ message: e.message || 'Failed to start scan.', type: 'error' });
    }
  };

  // Sort function
  function sortOpportunities(list: Opportunity[]): Opportunity[] {
    return [...list].sort((a, b) => {
      if (sortKey === 'score') return Math.abs(b.consensus_score ?? 0) - Math.abs(a.consensus_score ?? 0);
      if (sortKey === 'confidence') return (b.confidence ?? 0) - (a.confidence ?? 0);
      if (sortKey === 'change') return Math.abs(b.change_pct ?? 0) - Math.abs(a.change_pct ?? 0);
      return 0;
    });
  }

  const rawList = activeTab === 'longs' ? (data?.top_longs ?? []) : (data?.top_shorts ?? []);
  const displayed = sortOpportunities(rawList).map((item, i) => ({ ...item, rank: i + 1 }));

  const progress = data?.symbols_scanned ?? data?.progress ?? 0;
  const total = data?.total ?? 100;

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
      <View style={[styles.header, isDesktop && styles.headerDesktop]}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>Market Scanner</Text>
          {scanning && (
            <View style={styles.scanningIndicator}>
              <Animated.View style={[styles.scanDot, { opacity: scanPulse }]} />
              <Text style={styles.scanningText}>
                SCANNING {progress}/{total}
              </Text>
            </View>
          )}
        </View>
        <View style={styles.headerRight}>
          <MarketBadge />
          <Animated.View style={{ opacity: scanning ? scanPulse : 1 }}>
            <TouchableOpacity
              style={[styles.scanBtn, scanning && styles.scanBtnActive]}
              onPress={handleScanNow}
              disabled={scanning}
            >
              <Text style={styles.scanBtnText}>{scanning ? '⟳ Scanning...' : '⟳ Scan Now'}</Text>
            </TouchableOpacity>
          </Animated.View>
        </View>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>
            {error === 'UNAUTHORIZED' ? '⚠ Session expired' : '⚠ Could not reach API server'}
          </Text>
        </View>
      )}

      {/* Scanning progress bar */}
      {scanning && (
        <View style={styles.scanningSection}>
          <ScanProgressBar progress={progress} total={total} />
          <Text style={styles.scanProgressLabel}>
            Analyzing {progress}/{total} stocks...
          </Text>
        </View>
      )}

      {/* Status + countdown row */}
      {!scanning && (
        <View style={styles.statusRow}>
          <Text style={styles.statusText}>Last scan: {timeAgo(data?.last_scan ?? null)}</Text>
          {countdown > 0 && (
            <Text style={styles.countdownText}>
              Next scan in: {formatCountdown(countdown)}
            </Text>
          )}
        </View>
      )}

      {/* Stats strip */}
      <StatsStrip data={data} lastScan={data?.last_scan ?? null} />

      {/* Tab row + sort row */}
      <View style={[styles.controlsRow, isDesktop && styles.controlsRowDesktop]}>
        <View style={styles.tabRow}>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'longs' && styles.tabBtnActiveLong]}
            onPress={() => setActiveTab('longs')}
          >
            <Text style={[styles.tabBtnText, activeTab === 'longs' && { color: Colors.green }]}>
              ▲ LONGS
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'shorts' && styles.tabBtnActiveShort]}
            onPress={() => setActiveTab('shorts')}
          >
            <Text style={[styles.tabBtnText, activeTab === 'shorts' && { color: Colors.red }]}>
              ▼ SHORTS
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.sortRow}>
          <Text style={styles.sortLabel}>Sort:</Text>
          {(['score', 'confidence', 'change'] as SortKey[]).map(key => (
            <TouchableOpacity
              key={key}
              style={[styles.sortBtn, sortKey === key && styles.sortBtnActive]}
              onPress={() => setSortKey(key)}
            >
              <Text style={[styles.sortBtnText, sortKey === key && { color: Colors.primary }]}>
                {key === 'score' ? 'Score' : key === 'confidence' ? 'Conf' : 'Change%'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* List */}
      <FlatList
        key={`${activeTab}-${isDesktop ? 2 : 1}`}
        data={displayed}
        keyExtractor={item => `${item.symbol}-${activeTab}`}
        numColumns={isDesktop ? 2 : 1}
        contentContainerStyle={[styles.listContent, isDesktop && styles.listContentDesktop]}
        columnWrapperStyle={isDesktop ? styles.columnWrapper : undefined}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📡</Text>
            <Text style={styles.emptyTitle}>No Scan Data Yet</Text>
            <Text style={styles.emptyMsg}>Tap Scan Now to analyze the market.</Text>
            <TouchableOpacity style={styles.scanEmptyBtn} onPress={handleScanNow} disabled={scanning}>
              <Text style={styles.scanEmptyBtnText}>⟳ Start Scan</Text>
            </TouchableOpacity>
          </View>
        }
        renderItem={({ item }) => (
          <View style={isDesktop ? styles.cardWrapper : {}}>
            <OpportunityCard item={item} rank={item.rank ?? 1} />
          </View>
        )}
      />
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textSecondary, marginTop: 12, fontSize: 14 },

  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerDesktop: { paddingHorizontal: 24 },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.text, letterSpacing: 0.3 },

  scanningIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.primaryGlow,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: Colors.primary + '55',
  },
  scanDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
  },
  scanningText: { fontSize: 10, fontWeight: '700', color: Colors.primary, letterSpacing: 0.8 },

  scanBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  scanBtnActive: { backgroundColor: Colors.primaryDark },
  scanBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  // Error
  errorBanner: {
    marginHorizontal: 16,
    marginTop: 8,
    backgroundColor: Colors.redDim,
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: Colors.red + '44',
  },
  errorText: { color: Colors.red, fontSize: 13 },

  // Scanning section
  scanningSection: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 6,
  },
  progressTrack: {
    height: 4,
    backgroundColor: Colors.border,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: 4,
    backgroundColor: Colors.primary,
    borderRadius: 2,
  },
  scanProgressLabel: { fontSize: 12, color: Colors.textSecondary },

  // Status row
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  statusText: { fontSize: 12, color: Colors.textSecondary },
  countdownText: { fontSize: 12, color: Colors.textMuted },

  // Stats strip
  statsStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: Colors.surface,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: Colors.border,
    gap: 8,
  },
  stripItem: { fontSize: 12 },
  stripValue: { color: Colors.text, fontWeight: '700', fontSize: 12 },
  stripLabel: { color: Colors.textMuted, fontSize: 12 },
  stripSep: { color: Colors.border, fontSize: 12 },

  // Controls row
  controlsRow: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 10,
  },
  controlsRowDesktop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
  },
  tabRow: { flexDirection: 'row', gap: 8 },
  tabBtn: {
    flex: 1,
    height: 38,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  tabBtnActiveLong: { borderColor: Colors.green, backgroundColor: Colors.greenDim },
  tabBtnActiveShort: { borderColor: Colors.red, backgroundColor: Colors.redDim },
  tabBtnText: { fontSize: 12, fontWeight: '700', color: Colors.textSecondary, letterSpacing: 0.5 },

  sortRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sortLabel: { fontSize: 12, color: Colors.textMuted, marginRight: 2 },
  sortBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  sortBtnActive: { borderColor: Colors.primary, backgroundColor: Colors.primaryGlow },
  sortBtnText: { fontSize: 11, fontWeight: '600', color: Colors.textSecondary },

  // List
  listContent: { paddingBottom: 48, paddingHorizontal: 16 },
  listContentDesktop: { paddingHorizontal: 24 },
  columnWrapper: { gap: 12 },
  cardWrapper: { flex: 1 },

  // Opportunity card
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  rankText: { fontSize: 12, color: Colors.textMuted, fontWeight: '700', width: 26 },
  symbolText: { fontSize: 18, fontWeight: '800', color: Colors.text },

  badge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  badgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  scoreBarTrack: {
    height: 6,
    backgroundColor: Colors.border,
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 8,
  },
  scoreBarFill: {
    height: 6,
    borderRadius: 3,
  },

  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  priceText: { fontSize: 15, fontWeight: '700', color: Colors.text },
  changeText: { fontSize: 13, fontWeight: '600' },
  scoreLabel: { fontSize: 12, color: Colors.textSecondary },

  agentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  agentBadge: {
    borderRadius: 4,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderWidth: 1,
  },
  agentBadgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.3 },
  dirText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  reasonText: {
    fontSize: 12,
    color: Colors.textMuted,
    marginTop: 4,
    fontStyle: 'italic',
  },

  // Empty
  empty: { alignItems: 'center', paddingTop: 60, paddingBottom: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginBottom: 8 },
  emptyMsg: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  scanEmptyBtn: { backgroundColor: Colors.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  scanEmptyBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
