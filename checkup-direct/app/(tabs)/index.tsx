import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, RefreshControl, StyleSheet,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { StatCard } from '@/components/StatCard';
import { MiniChart } from '@/components/MiniChart';
import { apiGet } from '@/constants/Api';

interface PortfolioSummary {
  portfolio_value: number;
  equity: number;
  cash: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  long_positions: number;
  short_positions: number;
  net_exposure_pct: number;
  gross_exposure_pct: number;
  unrealized_pnl: number;
  last_updated: string;
}

interface EquityPoint { timestamp: string; value: number }

interface Position {
  symbol: string;
  side: string;
  entry_price: number;
  shares: number;
}

function fmt$(v: number) { return `$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }
function fmtPct(v: number) { return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%`; }
function pnlColor(v: number) { return v >= 0 ? Colors.green : Colors.red; }

export default function DashboardScreen() {
  const [summary, setSummary]   = useState<PortfolioSummary | null>(null);
  const [equity, setEquity]     = useState<EquityPoint[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [sum, eq, pos] = await Promise.all([
        apiGet<PortfolioSummary>('/api/portfolio/summary'),
        apiGet<EquityPoint[]>('/api/portfolio/equity-curve?days=30'),
        apiGet<{ positions: Position[] }>('/api/portfolio/positions'),
      ]);
      setSummary(sum);
      setEquity(eq);
      setPositions(pos.positions || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 15 seconds
  useEffect(() => {
    const interval = setInterval(load, 15_000);
    return () => clearInterval(interval);
  }, [load]);

  if (loading) return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={Colors.primary} />
      <Text style={styles.loadingText}>Loading portfolio…</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Portfolio</Text>
          {summary?.last_updated && (
            <Text style={styles.headerSub}>
              {new Date(summary.last_updated).toLocaleTimeString()}
            </Text>
          )}
        </View>

        {error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>⚠ {error === 'UNAUTHORIZED' ? 'Session expired' : 'Could not reach API server'}</Text>
          </View>
        )}

        {/* Portfolio Value */}
        <View style={styles.heroCard}>
          <Text style={styles.heroLabel}>TOTAL VALUE</Text>
          <Text style={styles.heroValue}>{fmt$(summary?.portfolio_value ?? 0)}</Text>
          <View style={styles.heroRow}>
            <Text style={[styles.heroPnl, { color: pnlColor(summary?.daily_pnl ?? 0) }]}>
              {summary && summary.daily_pnl >= 0 ? '▲' : '▼'} {fmt$(summary?.daily_pnl ?? 0)} today
            </Text>
            <Text style={[styles.heroPct, { color: pnlColor(summary?.daily_pnl_pct ?? 0) }]}>
              {fmtPct(summary?.daily_pnl_pct ?? 0)}
            </Text>
          </View>
        </View>

        {/* Equity Curve */}
        {equity.length > 1 && (
          <View style={styles.chartCard}>
            <Text style={styles.sectionTitle}>30-Day Equity</Text>
            <MiniChart data={equity} height={130} />
          </View>
        )}

        {/* Stats row */}
        <View style={styles.row}>
          <StatCard label="Cash" value={fmt$(summary?.cash ?? 0)} flex={1} />
          <View style={{ width: 8 }} />
          <StatCard label="Unrealised P&L" value={fmt$(summary?.unrealized_pnl ?? 0)}
            valueColor={pnlColor(summary?.unrealized_pnl ?? 0)} flex={1} />
        </View>

        <View style={styles.row}>
          <StatCard label="Long" value={String(summary?.long_positions ?? 0)} subValue="positions" flex={1} />
          <View style={{ width: 8 }} />
          <StatCard label="Short" value={String(summary?.short_positions ?? 0)} subValue="positions" flex={1} />
          <View style={{ width: 8 }} />
          <StatCard label="Net Exp." value={fmtPct(summary?.net_exposure_pct ?? 0)}
            valueColor={pnlColor(summary?.net_exposure_pct ?? 0)} flex={1} />
        </View>

        {/* Open Positions */}
        {positions.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Open Positions</Text>
            {positions.map((p, i) => (
              <View key={i} style={styles.positionRow}>
                <View style={styles.positionLeft}>
                  <Text style={styles.positionSymbol}>{p.symbol}</Text>
                  <View style={[styles.sideBadge, p.side === 'BUY' ? styles.longBadge : styles.shortBadge]}>
                    <Text style={styles.sideBadgeText}>{p.side === 'BUY' ? 'LONG' : 'SHORT'}</Text>
                  </View>
                </View>
                <View style={styles.positionRight}>
                  <Text style={styles.positionShares}>{p.shares} shares</Text>
                  <Text style={styles.positionEntry}>@ ${p.entry_price?.toFixed(2)}</Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textSecondary, marginTop: 12 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text },
  headerSub: { fontSize: 12, color: Colors.textMuted },
  errorBanner: { backgroundColor: '#3D1010', borderRadius: 8, padding: 12, marginBottom: 12 },
  errorText: { color: Colors.red, fontSize: 13 },
  heroCard: {
    backgroundColor: Colors.surface, borderRadius: 16, padding: 20,
    marginBottom: 12, borderWidth: 1, borderColor: Colors.border,
    alignItems: 'center',
  },
  heroLabel: { fontSize: 11, color: Colors.textSecondary, letterSpacing: 1.5, textTransform: 'uppercase' },
  heroValue: { fontSize: 42, fontWeight: '800', color: Colors.text, marginTop: 4 },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8 },
  heroPnl: { fontSize: 16, fontWeight: '600' },
  heroPct: { fontSize: 16, fontWeight: '600' },
  chartCard: { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: Colors.border },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 12 },
  row: { flexDirection: 'row', marginBottom: 8 },
  section: { marginTop: 8 },
  positionRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: Colors.surface, borderRadius: 12, padding: 14, marginBottom: 6,
    borderWidth: 1, borderColor: Colors.border,
  },
  positionLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  positionSymbol: { fontSize: 16, fontWeight: '700', color: Colors.text },
  sideBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  longBadge: { backgroundColor: Colors.green + '22' },
  shortBadge: { backgroundColor: Colors.red + '22' },
  sideBadgeText: { fontSize: 10, fontWeight: '700', color: Colors.green },
  positionRight: { alignItems: 'flex-end' },
  positionShares: { fontSize: 14, fontWeight: '600', color: Colors.text },
  positionEntry: { fontSize: 12, color: Colors.textSecondary },
});
