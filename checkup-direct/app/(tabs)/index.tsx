import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  Modal, TextInput, Pressable, ActivityIndicator, Alert, ScrollView
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet, apiPost, API_BASE_URL } from '@/constants/Api';

// Types
interface Position {
  id: number;
  symbol: string;
  quantity: number;
  avg_cost: number;
  direction: 'LONG' | 'SHORT';
  current_price: number | null;
  current_value: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  recommendation?: string;
  consensus_score?: number;
}

interface Summary {
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
}

// Helpers
function fmt$(v: number) {
  return `$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function pnlColor(v: number) {
  return v >= 0 ? Colors.green : Colors.red;
}

function recoBadgeColor(rec?: string): string {
  if (!rec) return Colors.textSecondary;
  const u = rec.toUpperCase();
  if (u === 'STRONG BUY')  return '#00D4AA';
  if (u === 'BUY')         return '#00A86B';
  if (u === 'HOLD')        return '#FFD700';
  if (u === 'SELL')        return '#FF8C00';
  if (u === 'STRONG SELL') return '#FF4757';
  return Colors.textSecondary;
}

// Direction Badge
function DirectionBadge({ direction }: { direction: 'LONG' | 'SHORT' }) {
  const isLong = direction === 'LONG';
  const color = isLong ? Colors.green : Colors.red;
  return (
    <View style={[styles.dirBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.dirBadgeText, { color }]}>{direction}</Text>
    </View>
  );
}

// Recommendation Badge
function RecoBadge({ rec }: { rec?: string }) {
  if (!rec) return null;
  const color = recoBadgeColor(rec);
  return (
    <View style={[styles.recoBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.recoBadgeText, { color }]}>{rec.toUpperCase()}</Text>
    </View>
  );
}

// Position Card
function PositionCard({ item, onDelete }: { item: Position; onDelete: () => void }) {
  const pnl = item.pnl ?? 0;
  const pnlPct = item.pnl_pct ?? 0;
  const hasPnl = item.pnl !== null;

  return (
    <View style={styles.posCard}>
      {/* Row 1: direction badge + symbol | P&L $ | ✕ button */}
      <View style={styles.posRow1}>
        <View style={styles.posRow1Left}>
          <DirectionBadge direction={item.direction} />
          <Text style={styles.posSymbol}>{item.symbol}</Text>
        </View>
        <View style={styles.posRow1Right}>
          {hasPnl && (
            <Text style={[styles.posPnlDollar, { color: pnlColor(pnl) }]}>
              {pnl >= 0 ? '+' : '-'}{fmt$(pnl)}
            </Text>
          )}
          <TouchableOpacity style={styles.deleteBtn} onPress={onDelete} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Text style={styles.deleteBtnText}>✕</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Row 2: Qty | Avg | Now */}
      <View style={styles.posRow2}>
        <Text style={styles.posMetaText}>Qty: {item.quantity}</Text>
        <Text style={styles.posMetaSep}>·</Text>
        <Text style={styles.posMetaText}>Avg: ${item.avg_cost.toFixed(2)}</Text>
        <Text style={styles.posMetaSep}>·</Text>
        <Text style={styles.posMetaText}>
          Now: {item.current_price != null ? `$${item.current_price.toFixed(2)}` : '—'}
        </Text>
      </View>

      {/* Row 3: P&L % | recommendation badge */}
      <View style={styles.posRow3}>
        {hasPnl && (
          <Text style={[styles.posPnlPct, { color: pnlColor(pnlPct) }]}>
            {fmtPct(pnlPct)}
          </Text>
        )}
        {item.recommendation && <RecoBadge rec={item.recommendation} />}
      </View>
    </View>
  );
}

// Add Position Modal
interface AddModalProps {
  visible: boolean;
  onClose: () => void;
  onAdded: () => void;
}

function AddPositionModal({ visible, onClose, onAdded }: AddModalProps) {
  const [symbol, setSymbol]       = useState('');
  const [quantity, setQuantity]   = useState('');
  const [avgCost, setAvgCost]     = useState('');
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG');
  const [saving, setSaving]       = useState(false);

  const reset = () => {
    setSymbol('');
    setQuantity('');
    setAvgCost('');
    setDirection('LONG');
  };

  const handleAdd = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) { Alert.alert('Error', 'Enter a symbol.'); return; }
    const qty = parseFloat(quantity);
    const cost = parseFloat(avgCost);
    if (!qty || qty <= 0) { Alert.alert('Error', 'Enter a valid quantity.'); return; }
    if (!cost || cost <= 0) { Alert.alert('Error', 'Enter a valid average cost.'); return; }

    setSaving(true);
    try {
      await apiPost('/api/positions/', { symbol: sym, quantity: qty, avg_cost: cost, direction });
      reset();
      onAdded();
      onClose();
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable style={styles.modalSheet} onPress={() => {}}>
          <Text style={styles.modalTitle}>Add Position</Text>

          <Text style={styles.modalLabel}>Symbol</Text>
          <TextInput
            style={styles.modalInput}
            value={symbol}
            onChangeText={t => setSymbol(t.toUpperCase())}
            autoCapitalize="characters"
            placeholder="e.g. AAPL"
            placeholderTextColor={Colors.textMuted}
          />

          <Text style={styles.modalLabel}>Quantity</Text>
          <TextInput
            style={styles.modalInput}
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="numeric"
            placeholder="e.g. 10"
            placeholderTextColor={Colors.textMuted}
          />

          <Text style={styles.modalLabel}>Average Cost</Text>
          <TextInput
            style={styles.modalInput}
            value={avgCost}
            onChangeText={setAvgCost}
            keyboardType="numeric"
            placeholder="$ per share"
            placeholderTextColor={Colors.textMuted}
          />

          <Text style={styles.modalLabel}>Direction</Text>
          <View style={styles.dirToggle}>
            <TouchableOpacity
              style={[styles.dirToggleBtn, direction === 'LONG' && { borderColor: Colors.green, backgroundColor: Colors.green + '22' }]}
              onPress={() => setDirection('LONG')}
            >
              <Text style={[styles.dirToggleBtnText, direction === 'LONG' && { color: Colors.green }]}>LONG</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.dirToggleBtn, direction === 'SHORT' && { borderColor: Colors.red, backgroundColor: Colors.red + '22' }]}
              onPress={() => setDirection('SHORT')}
            >
              <Text style={[styles.dirToggleBtnText, direction === 'SHORT' && { color: Colors.red }]}>SHORT</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            style={[styles.addBtn, saving && { opacity: 0.6 }]}
            onPress={handleAdd}
            disabled={saving}
          >
            {saving
              ? <ActivityIndicator color="#fff" size="small" />
              : <Text style={styles.addBtnText}>Add Position</Text>}
          </TouchableOpacity>

          <TouchableOpacity style={styles.cancelBtn} onPress={() => { reset(); onClose(); }}>
            <Text style={styles.cancelBtnText}>Cancel</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

// Main Screen
export default function PortfolioScreen() {
  const [positions, setPositions]   = useState<Position[]>([]);
  const [summary, setSummary]       = useState<Summary | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [showModal, setShowModal]   = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [pos, sum] = await Promise.all([
        apiGet<Position[]>('/api/positions/'),
        apiGet<Summary>('/api/positions/summary'),
      ]);
      setPositions(Array.isArray(pos) ? pos : []);
      setSummary(sum);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const handleDelete = (pos: Position) => {
    Alert.alert(
      'Delete position?',
      `Remove ${pos.symbol} from your portfolio?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete', style: 'destructive', onPress: async () => {
            try {
              const token = await AsyncStorage.getItem('auth_token');
              const res = await fetch(`${API_BASE_URL}/api/positions/${pos.id}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` },
              });
              if (!res.ok) throw new Error(`API error ${res.status}`);
              setPositions(prev => prev.filter(p => p.id !== pos.id));
            } catch (e: any) {
              Alert.alert('Error', e.message);
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading portfolio...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>My Portfolio</Text>
        <TouchableOpacity style={styles.addHeaderBtn} onPress={() => setShowModal(true)}>
          <Text style={styles.addHeaderBtnText}>+</Text>
        </TouchableOpacity>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>
            {error === 'UNAUTHORIZED' ? '⚠ Session expired' : '⚠ Could not reach API server'}
          </Text>
        </View>
      )}

      {/* Summary bar */}
      {summary && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.summaryBar}
        >
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Total Value</Text>
            <Text style={styles.summaryValue}>{fmt$(summary.total_value)}</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Daily P&L %</Text>
            <Text style={[styles.summaryValue, { color: pnlColor(summary.total_pnl) }]}>
              {fmtPct(summary.total_pnl_pct)}
            </Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Positions</Text>
            <Text style={styles.summaryValue}>{summary.position_count}</Text>
          </View>
        </ScrollView>
      )}

      <FlatList
        data={positions}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No positions yet{'\n'}Tap + to add your eToro holdings</Text>
          </View>
        }
        renderItem={({ item }) => (
          <PositionCard item={item} onDelete={() => handleDelete(item)} />
        )}
      />

      <AddPositionModal
        visible={showModal}
        onClose={() => setShowModal(false)}
        onAdded={load}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textSecondary, marginTop: 12 },

  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text },
  addHeaderBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.green,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addHeaderBtnText: { color: '#fff', fontWeight: '700', fontSize: 22, lineHeight: 26 },

  errorBanner: { marginHorizontal: 16, marginBottom: 8, backgroundColor: '#3D1010', borderRadius: 8, padding: 12 },
  errorText: { color: Colors.red, fontSize: 13 },

  summaryBar: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 0,
  },
  summaryItem: { alignItems: 'center', paddingHorizontal: 20 },
  summaryLabel: { fontSize: 11, color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 },
  summaryValue: { fontSize: 16, fontWeight: '700', color: Colors.text },
  summaryDivider: { width: 1, backgroundColor: Colors.border, marginVertical: 4 },

  listContent: { paddingHorizontal: 16, paddingBottom: 40, paddingTop: 8 },

  empty: { alignItems: 'center', paddingTop: 80 },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', lineHeight: 24, fontSize: 15 },

  posCard: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  posRow1: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  posRow1Left: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  posRow1Right: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  posSymbol: { fontSize: 18, fontWeight: '800', color: Colors.text },
  posPnlDollar: { fontSize: 16, fontWeight: '700' },
  deleteBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#3D1010',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.red,
  },
  deleteBtnText: { color: Colors.red, fontSize: 13, fontWeight: '700', lineHeight: 16 },

  posRow2: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  posMetaText: { fontSize: 13, color: Colors.textSecondary },
  posMetaSep: { fontSize: 13, color: Colors.textMuted },

  posRow3: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  posPnlPct: { fontSize: 13, fontWeight: '600' },

  dirBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1 },
  dirBadgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },

  recoBadge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  recoBadgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 48,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalTitle: { fontSize: 20, fontWeight: '800', color: Colors.text, marginBottom: 20, textAlign: 'center' },
  modalLabel: { fontSize: 12, color: Colors.textSecondary, marginBottom: 6, marginTop: 14 },
  modalInput: {
    backgroundColor: Colors.surfaceAlt,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    height: 46,
    paddingHorizontal: 14,
    color: Colors.text,
    fontSize: 15,
  },
  dirToggle: { flexDirection: 'row', gap: 10, marginTop: 4 },
  dirToggleBtn: {
    flex: 1,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surfaceAlt,
  },
  dirToggleBtnText: { fontSize: 14, fontWeight: '700', color: Colors.textSecondary },

  addBtn: {
    backgroundColor: Colors.green,
    borderRadius: 12,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
  },
  addBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  cancelBtn: { height: 48, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  cancelBtnText: { color: Colors.textSecondary, fontSize: 15 },
});
