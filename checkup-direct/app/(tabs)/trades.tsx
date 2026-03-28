import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, FlatList, RefreshControl, StyleSheet,
  ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet } from '@/constants/Api';

interface Trade {
  id: number;
  timestamp: string;
  symbol: string;
  action: string;
  shares: number;
  entry_price: number;
  signal_score: number;
  confidence: number;
  reasoning: string;
  portfolio_value: number;
}

interface TradeStats {
  total_trades: number;
  by_action: { action: string; count: number }[];
}

const ACTION_COLORS: Record<string, string> = {
  BUY:   Colors.green,
  SELL:  Colors.red,
  SHORT: '#FF6B9D',
  COVER: Colors.yellow,
};

function ActionChip({ action }: { action: string }) {
  const c = ACTION_COLORS[action] || Colors.textMuted;
  return (
    <View style={[styles.chip, { backgroundColor: c + '22', borderColor: c }]}>
      <Text style={[styles.chipText, { color: c }]}>{action}</Text>
    </View>
  );
}

function TradeRow({ trade }: { trade: Trade }) {
  const action = trade.action.toUpperCase();
  return (
    <View style={styles.tradeRow}>
      <View style={styles.tradeLeft}>
        <View style={styles.tradeTopRow}>
          <Text style={styles.tradeSymbol}>{trade.symbol}</Text>
          <ActionChip action={action} />
        </View>
        <Text style={styles.tradeTime}>
          {new Date(trade.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </Text>
      </View>
      <View style={styles.tradeRight}>
        <Text style={styles.tradeShares}>{trade.shares} shares</Text>
        <Text style={styles.tradePrice}>${trade.entry_price?.toFixed(2) ?? '—'}</Text>
      </View>
    </View>
  );
}

export default function TradesScreen() {
  const [trades, setTrades]   = useState<Trade[]>([]);
  const [stats, setStats]     = useState<TradeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [t, s] = await Promise.all([
        apiGet<Trade[]>('/api/trades/history?limit=100'),
        apiGet<TradeStats>('/api/trades/stats'),
      ]);
      setTrades(t);
      setStats(s);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const actionCounts = stats?.by_action?.reduce((acc, item) => {
    acc[item.action] = item.count;
    return acc;
  }, {} as Record<string, number>) ?? {};

  if (loading) return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={Colors.primary} />
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Trades</Text>
      </View>

      {error && <View style={styles.errorBanner}><Text style={styles.errorText}>⚠ {error}</Text></View>}

      {/* Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{stats?.total_trades ?? 0}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={[styles.statValue, { color: Colors.green }]}>{actionCounts['BUY'] ?? 0}</Text>
          <Text style={styles.statLabel}>Buys</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={[styles.statValue, { color: Colors.red }]}>{actionCounts['SELL'] ?? 0}</Text>
          <Text style={styles.statLabel}>Sells</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={[styles.statValue, { color: '#FF6B9D' }]}>{actionCounts['SHORT'] ?? 0}</Text>
          <Text style={styles.statLabel}>Shorts</Text>
        </View>
      </View>

      <FlatList
        data={trades}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        ListEmptyComponent={<View style={styles.empty}><Text style={styles.emptyText}>No trades yet. Start the bot to begin trading.</Text></View>}
        renderItem={({ item }) => <TradeRow trade={item} />}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  header: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text },
  errorBanner: { marginHorizontal: 16, marginBottom: 8, backgroundColor: '#3D1010', borderRadius: 8, padding: 12 },
  errorText: { color: Colors.red, fontSize: 13 },
  statsRow: { flexDirection: 'row', paddingHorizontal: 16, marginBottom: 12, gap: 8 },
  statBox: { flex: 1, backgroundColor: Colors.surface, borderRadius: 10, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: Colors.border },
  statValue: { fontSize: 22, fontWeight: '800', color: Colors.text },
  statLabel: { fontSize: 11, color: Colors.textSecondary, marginTop: 2, textTransform: 'uppercase' },
  tradeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 14, paddingHorizontal: 4 },
  tradeLeft: { flex: 1 },
  tradeTopRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  tradeSymbol: { fontSize: 16, fontWeight: '700', color: Colors.text },
  chip: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1 },
  chipText: { fontSize: 10, fontWeight: '700' },
  tradeTime: { fontSize: 12, color: Colors.textSecondary },
  tradeRight: { alignItems: 'flex-end' },
  tradeShares: { fontSize: 14, fontWeight: '600', color: Colors.text },
  tradePrice: { fontSize: 12, color: Colors.textSecondary },
  separator: { height: 1, backgroundColor: Colors.border, marginHorizontal: 4 },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', lineHeight: 22 },
});
