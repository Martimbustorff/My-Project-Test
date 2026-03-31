import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, RefreshControl, useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, recColor } from '@/constants/Colors';
import { apiGet } from '@/constants/Api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface MacroData {
  regime?: string;
  score_adjustment?: number;
  reasons?: string[];
  vix?: number;
  yield_curve?: number;
  fed_funds?: number;
  cpi?: number;
  unemployment?: number;
}

interface IndexQuote {
  symbol: string;
  label: string;
  price: number;
  change_pct: number;
}

interface TopOpportunity {
  symbol: string;
  direction: string;
  recommendation: string;
  consensus_score: number;
  confidence: number;
  price?: number;
  change_pct?: number;
  key_reasons?: string[];
}

interface ScannerResult {
  scanned_at?: string;
  top_longs?: TopOpportunity[];
  top_shorts?: TopOpportunity[];
}

const INDEX_SYMBOLS: { symbol: string; label: string }[] = [
  { symbol: 'SPY', label: 'S&P 500'    },
  { symbol: 'QQQ', label: 'NASDAQ'     },
  { symbol: 'IWM', label: 'Russell 2K' },
  { symbol: 'GLD', label: 'Gold'       },
  { symbol: 'TLT', label: 'Long Bonds' },
  { symbol: 'VXX', label: 'Volatility' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtPct(n?: number) {
  if (n == null) return '--';
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function fmtNum(n?: number, dec = 2) {
  if (n == null) return '--';
  return n.toFixed(dec);
}

function regimeInfo(regime?: string) {
  if (regime === 'risk_on')  return { label: 'RISK ON',  color: Colors.green,  desc: 'Conditions favour equities and growth assets' };
  if (regime === 'risk_off') return { label: 'RISK OFF', color: Colors.red,    desc: 'Elevated caution — defensive positioning preferred' };
  return                            { label: 'NEUTRAL',  color: Colors.yellow, desc: 'Mixed macro signals — balanced approach' };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <View style={styles.sectionRow}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {sub ? <Text style={styles.sectionSub}>{sub}</Text> : null}
    </View>
  );
}

function MacroPanel({ data, loading }: { data: MacroData | null; loading: boolean }) {
  const { label, color, desc } = regimeInfo(data?.regime);

  const indicators = [
    { key: 'VIX',          val: fmtNum(data?.vix, 1),                                             alert: (data?.vix ?? 0) > 25 },
    { key: 'Yield Curve',  val: data?.yield_curve != null ? fmtPct(data.yield_curve * 100) : '--', alert: (data?.yield_curve ?? 0) < 0 },
    { key: 'Fed Funds',    val: data?.fed_funds  != null ? `${fmtNum(data.fed_funds, 2)}%`  : '--', alert: false },
    { key: 'CPI YoY',      val: data?.cpi        != null ? `${fmtNum(data.cpi, 1)}%`        : '--', alert: (data?.cpi ?? 0) > 4 },
    { key: 'Unemployment', val: data?.unemployment != null ? `${fmtNum(data.unemployment, 1)}%` : '--', alert: false },
  ];

  return (
    <View style={styles.macroCard}>
      {loading ? (
        <ActivityIndicator size="small" color={Colors.primary} />
      ) : (
        <>
          <View style={styles.macroTop}>
            <View style={styles.macroLeft}>
              <Text style={styles.macroEyebrow}>MACRO REGIME</Text>
              <View style={[styles.regimePill, { borderColor: color }]}>
                <Text style={[styles.regimePillText, { color }]}>{label}</Text>
              </View>
              <Text style={styles.macroDesc}>{desc}</Text>
            </View>
            {data?.score_adjustment !== undefined && (
              <View style={styles.adjBlock}>
                <Text style={[styles.adjVal, { color: (data.score_adjustment ?? 0) >= 0 ? Colors.green : Colors.red }]}>
                  {(data.score_adjustment ?? 0) >= 0 ? '+' : ''}{((data.score_adjustment ?? 0) * 100).toFixed(0)}
                </Text>
                <Text style={styles.adjLabel}>pts adj.</Text>
              </View>
            )}
          </View>

          <View style={styles.indicatorsRow}>
            {indicators.map(ind => (
              <View key={ind.key} style={styles.indCell}>
                <Text style={styles.indKey}>{ind.key}</Text>
                <Text style={[styles.indVal, ind.alert && { color: Colors.red }]}>{ind.val}</Text>
              </View>
            ))}
          </View>

          {data?.reasons && data.reasons.length > 0 && (
            <View style={styles.chipsRow}>
              {data.reasons.map((r, i) => (
                <View key={i} style={styles.chip}>
                  <Text style={styles.chipText}>{r}</Text>
                </View>
              ))}
            </View>
          )}
        </>
      )}
    </View>
  );
}

function IndexCard({ q, loading }: { q?: IndexQuote; loading: boolean }) {
  if (loading || !q) {
    return <View style={styles.idxCard}><ActivityIndicator size="small" color={Colors.primary} /></View>;
  }
  const up = q.change_pct >= 0;
  const cc = up ? Colors.green : Colors.red;
  return (
    <View style={styles.idxCard}>
      <Text style={styles.idxSymbol}>{q.symbol}</Text>
      <Text style={styles.idxLabel}>{q.label}</Text>
      <Text style={styles.idxPrice}>
        {q.price > 0
          ? `$${q.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          : '--'}
      </Text>
      <View style={[styles.idxBadge, { backgroundColor: up ? Colors.greenDim : Colors.redDim }]}>
        <Text style={[styles.idxBadgeText, { color: cc }]}>{up ? '▲' : '▼'} {Math.abs(q.change_pct).toFixed(2)}%</Text>
      </View>
    </View>
  );
}

function OppRow({ item, rank }: { item: TopOpportunity; rank: number }) {
  const rc  = recColor(item.recommendation);
  const lng = item.direction === 'long';
  const sw  = Math.min(Math.abs(item.consensus_score ?? 0) * 100, 100);
  return (
    <View style={styles.oppRow}>
      <View style={styles.oppRank}><Text style={styles.oppRankText}>#{rank}</Text></View>
      <View style={styles.oppBody}>
        <View style={styles.oppTop}>
          <Text style={styles.oppSymbol}>{item.symbol}</Text>
          <View style={[styles.pill, { borderColor: lng ? Colors.green : Colors.red }]}>
            <Text style={[styles.pillText, { color: lng ? Colors.green : Colors.red }]}>
              {lng ? '▲ LONG' : '▼ SHORT'}
            </Text>
          </View>
          <View style={[styles.pill, { borderColor: rc }]}>
            <Text style={[styles.pillText, { color: rc }]}>{item.recommendation}</Text>
          </View>
          {item.change_pct != null && (
            <Text style={[styles.oppChg, { color: (item.change_pct ?? 0) >= 0 ? Colors.green : Colors.red }]}>
              {fmtPct(item.change_pct)}
            </Text>
          )}
        </View>
        <View style={styles.scoreBar}>
          <View style={[styles.scoreBarFill, { width: `${sw}%` as any, backgroundColor: rc }]} />
        </View>
        <View style={styles.oppMeta}>
          <Text style={styles.oppMetaText}>Score {(item.consensus_score ?? 0).toFixed(2)}</Text>
          <Text style={styles.oppMetaSep}> · </Text>
          <Text style={styles.oppMetaText}>Conf {((item.confidence ?? 0) * 100).toFixed(0)}%</Text>
          {item.price != null && (
            <>
              <Text style={styles.oppMetaSep}> · </Text>
              <Text style={styles.oppMetaText}>${item.price.toFixed(2)}</Text>
            </>
          )}
        </View>
        {item.key_reasons?.[0] ? (
          <Text style={styles.oppReason} numberOfLines={1}>{item.key_reasons[0]}</Text>
        ) : null}
      </View>
    </View>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────

export default function MarketScreen() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;

  const [macroData, setMacroData]           = useState<MacroData | null>(null);
  const [macroLoading, setMacroLoading]     = useState(true);
  const [macroError, setMacroError]         = useState('');
  const [indices, setIndices]               = useState<Record<string, IndexQuote>>({});
  const [indicesLoading, setIndicesLoading] = useState(true);
  const [scanData, setScanData]             = useState<ScannerResult | null>(null);
  const [scanLoading, setScanLoading]       = useState(true);
  const [refreshing, setRefreshing]         = useState(false);

  const loadMacro = useCallback(async () => {
    try {
      setMacroLoading(true);
      setMacroError('');
      const d = await apiGet('/api/insights/macro');
      setMacroData(d);
    } catch {
      setMacroError('Macro data unavailable — FRED API may be offline');
    } finally {
      setMacroLoading(false);
    }
  }, []);

  const loadIndices = useCallback(async () => {
    setIndicesLoading(true);
    const res: Record<string, IndexQuote> = {};
    await Promise.all(
      INDEX_SYMBOLS.map(async ({ symbol, label }) => {
        try {
          const d = await apiGet(`/api/analysis/${symbol}`);
          res[symbol] = { symbol, label, price: d.price ?? 0, change_pct: d.change_pct ?? 0 };
        } catch {
          res[symbol] = { symbol, label, price: 0, change_pct: 0 };
        }
      })
    );
    setIndices(res);
    setIndicesLoading(false);
  }, []);

  const loadScanner = useCallback(async () => {
    setScanLoading(true);
    try {
      const d = await apiGet('/api/scanner/results');
      setScanData(d);
    } catch {
      setScanData(null);
    } finally {
      setScanLoading(false);
    }
  }, []);

  const loadAll = useCallback(() => Promise.all([loadMacro(), loadIndices(), loadScanner()]), [loadMacro, loadIndices, loadScanner]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadAll();
    setRefreshing(false);
  }, [loadAll]);

  const topLongs  = scanData?.top_longs  ?? [];
  const topShorts = scanData?.top_shorts ?? [];
  const allOpps   = [...topLongs, ...topShorts]
    .sort((a, b) => Math.abs(b.consensus_score ?? 0) - Math.abs(a.consensus_score ?? 0))
    .slice(0, 8);

  const updatedStr = scanData?.scanned_at
    ? `Updated ${new Date(scanData.scanned_at).toLocaleTimeString()}`
    : 'From last scanner run';

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.content, isDesktop && styles.contentDesk]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Market Overview</Text>
            <Text style={styles.titleSub}>Macro regime · indices · top opportunities</Text>
          </View>
          <TouchableOpacity style={styles.refreshBtn} onPress={onRefresh}>
            <Text style={styles.refreshBtnText}>↻ Refresh</Text>
          </TouchableOpacity>
        </View>

        {/* Macro */}
        <MacroPanel data={macroData} loading={macroLoading} />
        {macroError ? <Text style={styles.errorBanner}>{macroError}</Text> : null}

        {/* Indices */}
        <SectionTitle title="Key Indices" sub="Via analysis engine" />
        <View style={[styles.idxGrid, isDesktop && styles.idxGridDesk]}>
          {INDEX_SYMBOLS.map(({ symbol, label }) => (
            <IndexCard
              key={symbol}
              q={indices[symbol] ? { ...indices[symbol], label } : undefined}
              loading={indicesLoading}
            />
          ))}
        </View>

        {/* Top Opportunities */}
        <SectionTitle title="Top Opportunities" sub={updatedStr} />
        {scanLoading ? (
          <View style={styles.loadRow}><ActivityIndicator color={Colors.primary} /><Text style={styles.loadText}>Loading…</Text></View>
        ) : allOpps.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyIcon}>🔭</Text>
            <Text style={styles.emptyText}>No scanner results yet.{'\n'}Go to Scanner and run a scan first.</Text>
          </View>
        ) : (
          <View style={styles.oppsCard}>
            {allOpps.map((item, i) => (
              <View key={item.symbol}>
                <OppRow item={item} rank={i + 1} />
                {i < allOpps.length - 1 && <View style={styles.divider} />}
              </View>
            ))}
          </View>
        )}

        {/* Desktop: side-by-side Longs / Shorts */}
        {!scanLoading && isDesktop && (topLongs.length > 0 || topShorts.length > 0) && (
          <View style={styles.splitRow}>
            <View style={styles.splitCol}>
              <SectionTitle title="Top Longs" />
              <View style={styles.oppsCard}>
                {topLongs.slice(0, 5).map((item, i) => (
                  <View key={item.symbol}>
                    <OppRow item={item} rank={i + 1} />
                    {i < Math.min(topLongs.length, 5) - 1 && <View style={styles.divider} />}
                  </View>
                ))}
              </View>
            </View>
            <View style={styles.splitCol}>
              <SectionTitle title="Top Shorts" />
              <View style={styles.oppsCard}>
                {topShorts.slice(0, 5).length > 0 ? topShorts.slice(0, 5).map((item, i) => (
                  <View key={item.symbol}>
                    <OppRow item={item} rank={i + 1} />
                    {i < Math.min(topShorts.length, 5) - 1 && <View style={styles.divider} />}
                  </View>
                )) : (
                  <Text style={styles.emptyColText}>No short signals</Text>
                )}
              </View>
            </View>
          </View>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root:         { flex: 1, backgroundColor: Colors.background },
  scroll:       { flex: 1 },
  content:      { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 40 },
  contentDesk:  { paddingHorizontal: 28, maxWidth: 1100, alignSelf: 'center' as any, width: '100%' },

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16, marginTop: 4 },
  title:        { fontSize: 22, fontWeight: '800', color: Colors.text, letterSpacing: -0.3 },
  titleSub:     { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  refreshBtn:   { backgroundColor: Colors.surface, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 7, borderWidth: 1, borderColor: Colors.border },
  refreshBtnText: { color: Colors.primary, fontSize: 13, fontWeight: '700' },

  errorBanner: { color: Colors.red, fontSize: 12, marginBottom: 12 },

  // Macro
  macroCard:  { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.border },
  macroTop:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 },
  macroLeft:  { flex: 1, gap: 6 },
  macroEyebrow: { fontSize: 10, fontWeight: '700', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 1 },
  regimePill:   { alignSelf: 'flex-start', borderRadius: 4, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 4 },
  regimePillText: { fontSize: 12, fontWeight: '800', letterSpacing: 1 },
  macroDesc:  { fontSize: 12, color: Colors.textSecondary, lineHeight: 16 },
  adjBlock:   { alignItems: 'center', paddingLeft: 12 },
  adjVal:     { fontSize: 22, fontWeight: '800' },
  adjLabel:   { fontSize: 10, color: Colors.textMuted },

  indicatorsRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginBottom: 10 },
  indCell:  { flex: 1, minWidth: 58, backgroundColor: Colors.surfaceAlt, borderRadius: 8, padding: 8, alignItems: 'center' },
  indKey:   { fontSize: 10, color: Colors.textMuted, marginBottom: 4, textAlign: 'center' },
  indVal:   { fontSize: 13, fontWeight: '700', color: Colors.text },

  chipsRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  chip:     { backgroundColor: Colors.surfaceAlt, borderRadius: 4, paddingHorizontal: 8, paddingVertical: 4, borderWidth: 1, borderColor: Colors.border },
  chipText: { fontSize: 11, color: Colors.textSecondary },

  // Section title
  sectionRow:   { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginBottom: 10, marginTop: 4 },
  sectionTitle: { fontSize: 13, fontWeight: '800', color: Colors.text, textTransform: 'uppercase', letterSpacing: 0.5 },
  sectionSub:   { fontSize: 11, color: Colors.textMuted },

  // Indices
  idxGrid:     { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 24 },
  idxGridDesk: { gap: 10 },
  idxCard:     { flex: 1, minWidth: 90, backgroundColor: Colors.surface, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  idxSymbol:   { fontSize: 13, fontWeight: '800', color: Colors.text, marginBottom: 2 },
  idxLabel:    { fontSize: 10, color: Colors.textMuted, marginBottom: 6 },
  idxPrice:    { fontSize: 13, fontWeight: '700', color: Colors.text, marginBottom: 6 },
  idxBadge:    { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 3 },
  idxBadgeText: { fontSize: 11, fontWeight: '700' },

  // Loading / empty
  loadRow:  { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 24 },
  loadText: { color: Colors.textSecondary, fontSize: 13 },
  emptyCard: { alignItems: 'center', paddingVertical: 36, gap: 8 },
  emptyIcon: { fontSize: 36 },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', lineHeight: 20, fontSize: 13 },
  emptyColText: { color: Colors.textMuted, padding: 14, fontSize: 13 },

  // Opps card
  oppsCard: { backgroundColor: Colors.surface, borderRadius: 14, borderWidth: 1, borderColor: Colors.border, overflow: 'hidden', marginBottom: 16 },
  divider:  { height: 1, backgroundColor: Colors.border },

  oppRow:     { flexDirection: 'row', alignItems: 'flex-start', padding: 12, gap: 10 },
  oppRank:    { width: 28, height: 28, borderRadius: 14, backgroundColor: Colors.surfaceAlt, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  oppRankText: { fontSize: 11, fontWeight: '700', color: Colors.textSecondary },
  oppBody:    { flex: 1 },
  oppTop:     { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 6 },
  oppSymbol:  { fontSize: 16, fontWeight: '800', color: Colors.text },
  pill:       { borderRadius: 4, borderWidth: 1, paddingHorizontal: 5, paddingVertical: 2 },
  pillText:   { fontSize: 10, fontWeight: '700', letterSpacing: 0.4 },
  oppChg:     { fontSize: 12, fontWeight: '700', marginLeft: 'auto' },
  scoreBar:   { height: 4, backgroundColor: Colors.border, borderRadius: 2, marginBottom: 6, overflow: 'hidden' },
  scoreBarFill: { height: 4, borderRadius: 2 },
  oppMeta:    { flexDirection: 'row', alignItems: 'center' },
  oppMetaText: { fontSize: 11, color: Colors.textSecondary },
  oppMetaSep: { fontSize: 11, color: Colors.textMuted },
  oppReason:  { fontSize: 11, color: Colors.textMuted, fontStyle: 'italic', marginTop: 4 },

  // Desktop split
  splitRow: { flexDirection: 'row', gap: 16 },
  splitCol: { flex: 1 },
});
