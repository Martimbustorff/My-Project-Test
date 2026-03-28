import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, FlatList, RefreshControl, StyleSheet,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet } from '@/constants/Api';

interface Signal {
  id: number;
  symbol: string;
  action: string;
  confidence: number;
  combined_score: number;
  technical_score: number;
  sentiment_score: number;
  momentum_score: number;
  fundamental_score: number;
  current_price: number;
  reasoning: string;
  timestamp: string;
}

const ACTION_COLORS: Record<string, string> = {
  BUY:   Colors.green,
  SELL:  Colors.red,
  SHORT: '#FF6B9D',
  COVER: Colors.yellow,
  HOLD:  Colors.textMuted,
};

function ActionBadge({ action }: { action: string }) {
  const a = action.replace('Action.', '');
  return (
    <View style={[styles.badge, { backgroundColor: (ACTION_COLORS[a] || Colors.textMuted) + '22', borderColor: ACTION_COLORS[a] || Colors.textMuted }]}>
      <Text style={[styles.badgeText, { color: ACTION_COLORS[a] || Colors.textMuted }]}>{a}</Text>
    </View>
  );
}

function ScoreBar({ value, label }: { value: number; label: string }) {
  const clamped = Math.max(-1, Math.min(1, value));
  const pct = ((clamped + 1) / 2) * 100;
  const color = clamped > 0 ? Colors.green : clamped < 0 ? Colors.red : Colors.textMuted;
  return (
    <View style={styles.scoreRow}>
      <Text style={styles.scoreLabel}>{label}</Text>
      <View style={styles.scoreBarBg}>
        <View style={styles.scoreBarMid} />
        <View style={[styles.scoreBarFill, {
          width: `${Math.abs(clamped) * 50}%`,
          left: clamped >= 0 ? '50%' : undefined,
          right: clamped < 0 ? '50%' : undefined,
          backgroundColor: color,
        }]} />
      </View>
      <Text style={[styles.scoreValue, { color }]}>{value >= 0 ? '+' : ''}{value.toFixed(2)}</Text>
    </View>
  );
}

function SignalCard({ item, expanded, onPress }: { item: Signal; expanded: boolean; onPress: () => void }) {
  const action = item.action.replace('Action.', '');
  const isActionable = !['HOLD'].includes(action);
  return (
    <TouchableOpacity style={[styles.card, !isActionable && styles.cardMuted]} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.cardHeader}>
        <View style={styles.cardLeft}>
          <Text style={styles.symbol}>{item.symbol}</Text>
          <Text style={styles.price}>${item.current_price?.toFixed(2)}</Text>
        </View>
        <View style={styles.cardRight}>
          <ActionBadge action={item.action} />
          <Text style={styles.confidence}>{(item.confidence * 100).toFixed(0)}% conf.</Text>
        </View>
      </View>

      {expanded && (
        <View style={styles.cardExpanded}>
          <ScoreBar value={item.technical_score}   label="Technical" />
          <ScoreBar value={item.sentiment_score}   label="Sentiment" />
          <ScoreBar value={item.momentum_score}    label="Momentum"  />
          <ScoreBar value={item.fundamental_score} label="Fundamental" />
          {item.reasoning && (() => {
            try {
              const reasons: string[] = JSON.parse(item.reasoning);
              return reasons.slice(0, 3).map((r, i) => (
                <Text key={i} style={styles.reasoning}>• {r}</Text>
              ));
            } catch { return <Text style={styles.reasoning}>{item.reasoning}</Text>; }
          })()}
          <Text style={styles.timestamp}>{new Date(item.timestamp).toLocaleString()}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

type Filter = 'all' | 'actionable';

export default function SignalsScreen() {
  const [signals, setSignals]     = useState<Signal[]>([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter]       = useState<Filter>('actionable');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError]         = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await apiGet<Signal[]>('/api/signals/latest?limit=100');
      setSignals(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const i = setInterval(load, 30_000);
    return () => clearInterval(i);
  }, [load]);

  const displayed = filter === 'actionable'
    ? signals.filter(s => !['HOLD', 'Action.HOLD'].includes(s.action))
    : signals;

  if (loading) return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={Colors.primary} />
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Signals</Text>
        <View style={styles.filterRow}>
          {(['actionable', 'all'] as Filter[]).map(f => (
            <TouchableOpacity key={f} style={[styles.filterBtn, filter === f && styles.filterBtnActive]} onPress={() => setFilter(f)}>
              <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
                {f === 'actionable' ? '⚡ Actionable' : '📋 All'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {error && <View style={styles.errorBanner}><Text style={styles.errorText}>⚠ {error}</Text></View>}

      <FlatList
        data={displayed}
        keyExtractor={item => String(item.id ?? item.symbol)}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={Colors.primary} />}
        ListEmptyComponent={<View style={styles.empty}><Text style={styles.emptyText}>No {filter === 'actionable' ? 'actionable ' : ''}signals yet. Is the bot running?</Text></View>}
        renderItem={({ item }) => (
          <SignalCard
            item={item}
            expanded={expandedId === item.id}
            onPress={() => setExpandedId(expandedId === item.id ? null : item.id)}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  header: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text, marginBottom: 12 },
  filterRow: { flexDirection: 'row', gap: 8 },
  filterBtn: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border },
  filterBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterText: { fontSize: 13, color: Colors.textSecondary, fontWeight: '600' },
  filterTextActive: { color: '#fff' },
  errorBanner: { margin: 16, backgroundColor: '#3D1010', borderRadius: 8, padding: 12 },
  errorText: { color: Colors.red, fontSize: 13 },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', lineHeight: 22 },
  card: { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: Colors.border },
  cardMuted: { opacity: 0.6 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  cardLeft: {},
  cardRight: { alignItems: 'flex-end', gap: 4 },
  symbol: { fontSize: 18, fontWeight: '700', color: Colors.text },
  price: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  badge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  badgeText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  confidence: { fontSize: 12, color: Colors.textSecondary },
  cardExpanded: { marginTop: 14, paddingTop: 14, borderTopWidth: 1, borderTopColor: Colors.border },
  scoreRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  scoreLabel: { width: 80, fontSize: 11, color: Colors.textSecondary },
  scoreBarBg: { flex: 1, height: 6, backgroundColor: Colors.surfaceAlt, borderRadius: 3, overflow: 'hidden', position: 'relative' },
  scoreBarMid: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, backgroundColor: Colors.border },
  scoreBarFill: { position: 'absolute', top: 0, bottom: 0, borderRadius: 3 },
  scoreValue: { width: 40, fontSize: 11, fontWeight: '600', textAlign: 'right' },
  reasoning: { fontSize: 12, color: Colors.textSecondary, marginBottom: 4, lineHeight: 18 },
  timestamp: { fontSize: 11, color: Colors.textMuted, marginTop: 8 },
});
