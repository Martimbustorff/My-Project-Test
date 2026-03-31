import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  Modal, TextInput, Pressable, ActivityIndicator,
  ScrollView, useWindowDimensions, Animated,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, recColor } from '@/constants/Colors';
import { Sparkline } from '@/components/Sparkline';
import { MarketBadge } from '@/components/MarketBadge';
import { useToast } from '@/components/Toast';
import { apiGet, apiPost, API_BASE_URL } from '@/constants/Api';

// ─── Types ────────────────────────────────────────────────────────────────────

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt$(v: number) {
  return `$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function pnlColor(v: number) {
  return v >= 0 ? Colors.green : Colors.red;
}

function generateSparklineData(avgCost: number, currentPrice: number): number[] {
  if (!avgCost || !currentPrice) return [];
  const points = 20;
  const data: number[] = [];
  for (let i = 0; i < points; i++) {
    const progress = i / (points - 1);
    const base = avgCost + (currentPrice - avgCost) * (progress * progress * (3 - 2 * progress));
    const noise = (Math.random() - 0.5) * Math.abs(currentPrice - avgCost) * 0.1;
    data.push(base + noise);
  }
  data[data.length - 1] = currentPrice;
  return data;
}

// ─── Direction Badge ──────────────────────────────────────────────────────────

function DirectionBadge({ direction }: { direction: 'LONG' | 'SHORT' }) {
  const isLong = direction === 'LONG';
  const color = isLong ? Colors.green : Colors.red;
  return (
    <View style={[styles.dirBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.dirBadgeText, { color }]}>{isLong ? '▲' : '▼'} {direction}</Text>
    </View>
  );
}

// ─── Recommendation Badge ─────────────────────────────────────────────────────

function RecoBadge({ rec }: { rec?: string }) {
  if (!rec) return null;
  const color = recColor(rec);
  return (
    <View style={[styles.recoBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.recoBadgeText, { color }]}>{rec.toUpperCase()}</Text>
    </View>
  );
}

// ─── Stat Item ────────────────────────────────────────────────────────────────

function StatItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.statItem}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : {}]}>{value}</Text>
    </View>
  );
}

// ─── Position Card ────────────────────────────────────────────────────────────

function PositionCard({
  item,
  onDelete,
  cardWidth,
}: {
  item: Position;
  onDelete: () => void;
  cardWidth: number;
}) {
  const pnl = item.pnl ?? 0;
  const pnlPct = item.pnl_pct ?? 0;
  const hasPnl = item.pnl !== null;
  const currentPrice = item.current_price ?? item.avg_cost;
  const sparkData = generateSparklineData(item.avg_cost, currentPrice);

  return (
    <View style={[styles.posCard, { width: cardWidth }]}>
      {/* Header row: direction | symbol | price | ✕ */}
      <View style={styles.posRow1}>
        <DirectionBadge direction={item.direction} />
        <Text style={styles.posSymbol}>{item.symbol}</Text>
        <View style={{ flex: 1 }} />
        {item.current_price != null && (
          <Text style={styles.posCurrentPrice}>${item.current_price.toFixed(2)}</Text>
        )}
        <TouchableOpacity
          style={styles.deleteBtn}
          onPress={onDelete}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={styles.deleteBtnText}>✕</Text>
        </TouchableOpacity>
      </View>

      {/* Sparkline */}
      {sparkData.length >= 2 && (
        <View style={styles.sparklineWrapper}>
          <Sparkline
            data={sparkData}
            width={cardWidth - 28}
            height={44}
            showArea
          />
        </View>
      )}

      {/* Stats row */}
      <View style={styles.statsRow}>
        <StatItem label="Qty" value={String(item.quantity)} />
        <View style={styles.statDivider} />
        <StatItem label="Avg" value={`$${item.avg_cost.toFixed(2)}`} />
        {hasPnl && (
          <>
            <View style={styles.statDivider} />
            <StatItem label="P&L" value={`${pnl >= 0 ? '+' : '-'}${fmt$(pnl)}`} color={pnlColor(pnl)} />
            <View style={styles.statDivider} />
            <StatItem label="%" value={fmtPct(pnlPct)} color={pnlColor(pnlPct)} />
          </>
        )}
      </View>

      {/* Recommendation badge */}
      {item.recommendation && (
        <View style={styles.recoRow}>
          <RecoBadge rec={item.recommendation} />
          {item.consensus_score != null && (
            <Text style={styles.scoreText}>
              Score:{' '}
              <Text style={{ color: (item.consensus_score ?? 0) >= 0 ? Colors.green : Colors.red }}>
                {(item.consensus_score ?? 0).toFixed(2)}
              </Text>
            </Text>
          )}
        </View>
      )}
    </View>
  );
}

// ─── Hero Card ────────────────────────────────────────────────────────────────

function HeroCard({ summary }: { summary: Summary }) {
  const pnl = summary.total_pnl ?? 0;
  const pnlPct = summary.total_pnl_pct ?? 0;
  const isPositive = pnl >= 0;
  const sparkPoints = Array.from({ length: 20 }, (_, i) => {
    const base = summary.total_cost + (pnl * i) / 19;
    return base + (Math.random() - 0.5) * Math.abs(pnl) * 0.05;
  });
  if (sparkPoints.length) sparkPoints[sparkPoints.length - 1] = summary.total_value;

  return (
    <View style={styles.heroCard}>
      <Text style={styles.heroLabel}>Portfolio Performance</Text>
      <Text style={styles.heroValue}>{fmt$(summary.total_value)}</Text>
      <View style={styles.heroSubRow}>
        <Text style={[styles.heroArrow, { color: pnlColor(pnl) }]}>
          {isPositive ? '▲' : '▼'}
        </Text>
        <Text style={[styles.heroPnl, { color: pnlColor(pnl) }]}>
          {isPositive ? '+' : '-'}{fmt$(pnl)}
        </Text>
        <View style={[styles.heroPctBadge, { backgroundColor: pnlColor(pnl) + '22', borderColor: pnlColor(pnl) }]}>
          <Text style={[styles.heroPct, { color: pnlColor(pnl) }]}>{fmtPct(pnlPct)}</Text>
        </View>
      </View>
      <View style={styles.heroSparkline}>
        <Sparkline data={sparkPoints} width={200} height={60} showArea />
      </View>
    </View>
  );
}

// ─── Metrics Panel ────────────────────────────────────────────────────────────

function MetricsPanel({ summary, positions }: { summary: Summary; positions: Position[] }) {
  const longCount = positions.filter(p => p.direction === 'LONG').length;
  const shortCount = positions.filter(p => p.direction === 'SHORT').length;

  return (
    <View style={styles.metricsPanel}>
      <Text style={styles.metricsPanelTitle}>Portfolio Metrics</Text>
      <View style={styles.metricRow}>
        <Text style={styles.metricLabel}>Total Cost</Text>
        <Text style={styles.metricValue}>{fmt$(summary.total_cost ?? 0)}</Text>
      </View>
      <View style={styles.metricDivider} />
      <View style={styles.metricRow}>
        <Text style={styles.metricLabel}>Unrealized P&L</Text>
        <Text style={[styles.metricValue, { color: pnlColor(summary.total_pnl ?? 0) }]}>
          {(summary.total_pnl ?? 0) >= 0 ? '+' : '-'}{fmt$(summary.total_pnl ?? 0)}
        </Text>
      </View>
      <View style={styles.metricDivider} />
      <View style={styles.metricRow}>
        <Text style={styles.metricLabel}>Positions</Text>
        <Text style={styles.metricValue}>{summary.position_count ?? 0}</Text>
      </View>
      <View style={styles.metricDivider} />
      <View style={styles.metricRow}>
        <Text style={styles.metricLabel}>Long / Short</Text>
        <View style={styles.metricLongShort}>
          <Text style={[styles.metricValue, { color: Colors.green }]}>{longCount}</Text>
          <Text style={styles.metricSlash}> / </Text>
          <Text style={[styles.metricValue, { color: Colors.red }]}>{shortCount}</Text>
        </View>
      </View>
    </View>
  );
}

// ─── Add Position Modal ───────────────────────────────────────────────────────

interface AddModalProps {
  visible: boolean;
  onClose: () => void;
  onAdded: () => void;
}

function AddPositionModal({ visible, onClose, onAdded }: AddModalProps) {
  const toast = useToast();
  const [symbol, setSymbol]       = useState('');
  const [quantity, setQuantity]   = useState('');
  const [avgCost, setAvgCost]     = useState('');
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG');
  const [saving, setSaving]       = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const reset = () => {
    setSymbol('');
    setQuantity('');
    setAvgCost('');
    setDirection('LONG');
    setFocusedField(null);
  };

  const handleAdd = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) { toast.show({ message: 'Please enter a symbol.', type: 'error' }); return; }
    const qty = parseFloat(quantity);
    const cost = parseFloat(avgCost);
    if (!qty || qty <= 0) { toast.show({ message: 'Enter a valid quantity.', type: 'error' }); return; }
    if (!cost || cost <= 0) { toast.show({ message: 'Enter a valid average cost.', type: 'error' }); return; }

    setSaving(true);
    try {
      await apiPost('/api/positions/', { symbol: sym, quantity: qty, avg_cost: cost, direction });
      toast.show({ message: `${sym} added to portfolio!`, type: 'success' });
      reset();
      onAdded();
      onClose();
    } catch (e: any) {
      toast.show({ message: e.message || 'Failed to add position.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = (field: string) => [
    styles.modalInput,
    focusedField === field && { borderColor: Colors.borderFocus, backgroundColor: Colors.surfaceHover },
  ];

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.modalOverlay} onPress={onClose}>
        <Pressable style={styles.modalSheet} onPress={() => {}}>
          <View style={styles.modalHandle} />
          <Text style={styles.modalTitle}>Add Position</Text>

          <Text style={styles.modalLabel}>Symbol</Text>
          <TextInput
            style={inputStyle('symbol')}
            value={symbol}
            onChangeText={t => setSymbol(t.toUpperCase())}
            onFocus={() => setFocusedField('symbol')}
            onBlur={() => setFocusedField(null)}
            autoCapitalize="characters"
            placeholder="e.g. AAPL"
            placeholderTextColor={Colors.textMuted}
          />

          <Text style={styles.modalLabel}>Quantity</Text>
          <TextInput
            style={inputStyle('quantity')}
            value={quantity}
            onChangeText={setQuantity}
            onFocus={() => setFocusedField('quantity')}
            onBlur={() => setFocusedField(null)}
            keyboardType="numeric"
            placeholder="e.g. 10"
            placeholderTextColor={Colors.textMuted}
          />

          <Text style={styles.modalLabel}>Average Cost per Share</Text>
          <TextInput
            style={inputStyle('avgCost')}
            value={avgCost}
            onChangeText={setAvgCost}
            onFocus={() => setFocusedField('avgCost')}
            onBlur={() => setFocusedField(null)}
            keyboardType="numeric"
            placeholder="$ per share"
            placeholderTextColor={Colors.textMuted}
          />

          <Text style={styles.modalLabel}>Direction</Text>
          <View style={styles.dirToggle}>
            <TouchableOpacity
              style={[
                styles.dirToggleBtn,
                direction === 'LONG' && { borderColor: Colors.green, backgroundColor: Colors.green + '22' },
              ]}
              onPress={() => setDirection('LONG')}
            >
              <Text style={[styles.dirToggleBtnText, direction === 'LONG' && { color: Colors.green }]}>
                ▲ LONG
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.dirToggleBtn,
                direction === 'SHORT' && { borderColor: Colors.red, backgroundColor: Colors.red + '22' },
              ]}
              onPress={() => setDirection('SHORT')}
            >
              <Text style={[styles.dirToggleBtnText, direction === 'SHORT' && { color: Colors.red }]}>
                ▼ SHORT
              </Text>
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

// ─── Main Screen ──────────────────────────────────────────────────────────────

export default function PortfolioScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;
  const toast = useToast();

  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary]     = useState<Summary | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

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

  const handleDelete = async (pos: Position) => {
    try {
      const token = await AsyncStorage.getItem('auth_token');
      const res = await fetch(`${API_BASE_URL}/api/positions/${pos.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setPositions(prev => prev.filter(p => p.id !== pos.id));
      toast.show({ message: `${pos.symbol} removed from portfolio.`, type: 'info' });
    } catch (e: any) {
      toast.show({ message: e.message || 'Failed to delete position.', type: 'error' });
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Loading portfolio...</Text>
      </View>
    );
  }

  // Card width calculation
  const contentPad = isDesktop ? 24 : 16;
  const gridGap = 12;
  const availableWidth = width - contentPad * 2;
  const numColumns = isDesktop ? 2 : 1;
  const cardWidth = numColumns === 2
    ? Math.floor((availableWidth - gridGap) / 2)
    : availableWidth;

  // Error state
  if (error && positions.length === 0) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>My Portfolio</Text>
          <MarketBadge />
        </View>
        <View style={styles.errorState}>
          <Text style={styles.errorStateIcon}>⚠</Text>
          <Text style={styles.errorStateTitle}>API Server Offline</Text>
          <Text style={styles.errorStateMsg}>{error === 'UNAUTHORIZED' ? 'Session expired. Please log in again.' : 'Could not reach the API server.'}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryBtnText}>⟳  Retry</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={[styles.header, isDesktop && styles.headerDesktop]}>
        <Text style={styles.headerTitle}>My Portfolio</Text>
        <View style={styles.headerRight}>
          <MarketBadge />
          <TouchableOpacity style={styles.addHeaderBtn} onPress={() => setShowModal(true)}>
            <Text style={styles.addHeaderBtnText}>+ Add</Text>
          </TouchableOpacity>
        </View>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>
            {error === 'UNAUTHORIZED' ? '⚠ Session expired' : '⚠ Could not reach API server'}
          </Text>
        </View>
      )}

      <ScrollView contentContainerStyle={[styles.scrollContent, isDesktop && styles.scrollContentDesktop]}>
        {/* Hero + Metrics row (desktop: side by side) */}
        {summary && (
          <View style={[styles.topSection, isDesktop && styles.topSectionDesktop]}>
            <View style={isDesktop ? styles.heroWrapper : {}}>
              <HeroCard summary={summary} />
            </View>
            <View style={isDesktop ? styles.metricsWrapper : {}}>
              <MetricsPanel summary={summary} positions={positions} />
            </View>
          </View>
        )}

        {/* Positions grid */}
        <View style={[styles.positionsSection, isDesktop && { paddingHorizontal: contentPad }]}>
          <Text style={styles.sectionTitle}>
            Positions
            <Text style={styles.sectionCount}> ({positions.length})</Text>
          </Text>

          {positions.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyIcon}>📊</Text>
              <Text style={styles.emptyTitle}>No Positions Yet</Text>
              <Text style={styles.emptyMsg}>Add your first position to start tracking your portfolio.</Text>
              <TouchableOpacity style={styles.emptyAddBtn} onPress={() => setShowModal(true)}>
                <Text style={styles.emptyAddBtnText}>+ Add Position</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={[styles.grid, isDesktop && styles.gridDesktop]}>
              {positions.map(item => (
                <PositionCard
                  key={item.id}
                  item={item}
                  onDelete={() => handleDelete(item)}
                  cardWidth={cardWidth}
                />
              ))}
            </View>
          )}
        </View>
      </ScrollView>

      <AddPositionModal
        visible={showModal}
        onClose={() => setShowModal(false)}
        onAdded={load}
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
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.text, letterSpacing: 0.3 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  addHeaderBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  addHeaderBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  // Error states
  errorBanner: { marginHorizontal: 16, marginTop: 8, backgroundColor: Colors.redDim, borderRadius: 8, padding: 12, borderWidth: 1, borderColor: Colors.red + '44' },
  errorText: { color: Colors.red, fontSize: 13 },
  errorState: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  errorStateIcon: { fontSize: 40, marginBottom: 16 },
  errorStateTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginBottom: 8 },
  errorStateMsg: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  retryBtn: { backgroundColor: Colors.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  retryBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },

  // Scroll
  scrollContent: { paddingBottom: 48 },
  scrollContentDesktop: {},

  // Top section
  topSection: { padding: 16, gap: 12 },
  topSectionDesktop: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    paddingTop: 20,
    gap: 16,
    alignItems: 'stretch',
  },
  heroWrapper: { flex: 3 },
  metricsWrapper: { flex: 2 },

  // Hero card
  heroCard: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  heroLabel: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 6 },
  heroValue: { fontSize: 28, fontWeight: '800', color: Colors.text, letterSpacing: 0.5, marginBottom: 8 },
  heroSubRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  heroArrow: { fontSize: 16, fontWeight: '700' },
  heroPnl: { fontSize: 18, fontWeight: '700' },
  heroPctBadge: {
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  heroPct: { fontSize: 13, fontWeight: '700' },
  heroSparkline: { marginTop: 4 },

  // Metrics panel
  metricsPanel: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  metricsPanelTitle: { fontSize: 11, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 12 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8 },
  metricDivider: { height: 1, backgroundColor: Colors.border },
  metricLabel: { fontSize: 13, color: Colors.textSecondary },
  metricValue: { fontSize: 14, fontWeight: '700', color: Colors.text },
  metricLongShort: { flexDirection: 'row', alignItems: 'center' },
  metricSlash: { color: Colors.textMuted, fontSize: 14 },

  // Positions section
  positionsSection: { paddingHorizontal: 16, paddingTop: 8 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 },
  sectionCount: { color: Colors.textMuted, fontWeight: '400' },

  // Grid
  grid: { gap: 12 },
  gridDesktop: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },

  // Position card
  posCard: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  posRow1: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  posSymbol: { fontSize: 17, fontWeight: '800', color: Colors.text },
  posCurrentPrice: { fontSize: 14, fontWeight: '600', color: Colors.textSecondary },
  deleteBtn: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: Colors.redDim,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.red + '55',
  },
  deleteBtnText: { color: Colors.red, fontSize: 12, fontWeight: '700', lineHeight: 14 },

  sparklineWrapper: { marginBottom: 10, overflow: 'hidden', borderRadius: 4 },

  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surfaceAlt,
    borderRadius: 8,
    padding: 10,
    gap: 0,
    marginBottom: 8,
  },
  statItem: { flex: 1, alignItems: 'center' },
  statLabel: { fontSize: 10, color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 2 },
  statValue: { fontSize: 12, fontWeight: '700', color: Colors.text },
  statDivider: { width: 1, height: 24, backgroundColor: Colors.border },

  recoRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scoreText: { fontSize: 12, color: Colors.textSecondary },

  // Direction badge
  dirBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, borderWidth: 1 },
  dirBadgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },

  // Reco badge
  recoBadge: { borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  recoBadgeText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },

  // Empty state
  empty: { alignItems: 'center', paddingTop: 60, paddingBottom: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginBottom: 8 },
  emptyMsg: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  emptyAddBtn: { backgroundColor: Colors.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  emptyAddBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.80)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 48,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalHandle: {
    width: 36,
    height: 4,
    backgroundColor: Colors.border,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 20,
  },
  modalTitle: { fontSize: 20, fontWeight: '800', color: Colors.text, marginBottom: 20, textAlign: 'center' },
  modalLabel: { fontSize: 12, color: Colors.textSecondary, marginBottom: 6, marginTop: 14, letterSpacing: 0.5 },
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
    backgroundColor: Colors.primary,
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
