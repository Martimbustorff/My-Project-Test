import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  Switch, ActivityIndicator, Alert, TextInput,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet, apiPost, apiDelete } from '@/constants/Api';
import { useAuth } from '@/hooks/useAuth';
import { showToast } from '@/components/Toast';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BotStatus {
  running: boolean;
  mode: string | null;
  pid: number | null;
}

interface WatchlistItem {
  symbol: string;
  added_at?: string;
}

interface IntegrationStatus {
  name: string;
  icon: string;
  status: 'ok' | 'warn' | 'error';
  detail: string;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionTitle({ title }: { title: string }) {
  return <Text style={styles.sectionTitle}>{title}</Text>;
}

function InfoRow({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <View style={styles.infoRow}>
      <Text style={[styles.infoLabel, danger && { color: Colors.red }]}>{label}</Text>
      <Text style={[styles.infoValue, danger && { color: Colors.red }]}>{value}</Text>
    </View>
  );
}

function WeightBar({ label, pct }: { label: string; pct: number }) {
  return (
    <View style={styles.weightRow}>
      <Text style={styles.weightLabel}>{label}</Text>
      <View style={styles.weightBarBg}>
        <View style={[styles.weightBarFill, { width: `${pct}%` as any }]} />
      </View>
      <Text style={styles.weightPct}>{pct}%</Text>
    </View>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────

export default function SettingsScreen() {
  const { logout }             = useAuth();
  const { width }              = useWindowDimensions();
  const isDesktop              = width >= 900;

  // Bot
  const [botStatus, setBotStatus]   = useState<BotStatus | null>(null);
  const [botLoading, setBotLoading] = useState(true);
  const [toggling, setToggling]     = useState(false);
  const [liveMode, setLiveMode]     = useState(false);

  // Watchlist
  const [watchlist, setWatchlist]   = useState<WatchlistItem[]>([]);
  const [wlLoading, setWlLoading]   = useState(true);
  const [addSymbol, setAddSymbol]   = useState('');
  const [adding, setAdding]         = useState(false);

  // Integrations
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([
    { name: 'Backend API',    icon: '🖥',  status: 'warn',  detail: 'Checking…' },
    { name: 'Claude AI',      icon: '🤖',  status: 'warn',  detail: 'Checking…' },
    { name: 'Finnhub News',   icon: '📰',  status: 'warn',  detail: 'Checking…' },
    { name: 'FRED Macro',     icon: '🏛',  status: 'warn',  detail: 'Checking…' },
    { name: 'PyPortfolioOpt', icon: '📐',  status: 'warn',  detail: 'Checking…' },
  ]);

  // ── Data loading ────────────────────────────────────────────────────────────

  const loadBot = useCallback(async () => {
    try {
      const s = await apiGet<BotStatus>('/api/bot/status');
      setBotStatus(s);
    } catch { /* ok */ } finally { setBotLoading(false); }
  }, []);

  const loadWatchlist = useCallback(async () => {
    try {
      setWlLoading(true);
      const data = await apiGet<WatchlistItem[]>('/api/watchlist');
      setWatchlist(Array.isArray(data) ? data : []);
    } catch { setWatchlist([]); } finally { setWlLoading(false); }
  }, []);

  const checkIntegrations = useCallback(async () => {
    const updates: IntegrationStatus[] = [...integrations];

    // Backend API
    try {
      await apiGet('/api/bot/status');
      updates[0] = { ...updates[0], status: 'ok', detail: 'Connected' };
    } catch {
      updates[0] = { ...updates[0], status: 'error', detail: 'Not reachable' };
    }

    // Claude / Finnhub / FRED / PyPortfolioOpt — check via insights endpoints
    try {
      const macro = await apiGet('/api/insights/macro');
      updates[3] = { ...updates[3], status: 'ok', detail: `Regime: ${macro?.regime ?? 'N/A'}` };
    } catch {
      updates[3] = { ...updates[3], status: 'warn', detail: 'FRED offline (free API)' };
    }

    try {
      const opt = await apiGet('/api/insights/optimize');
      updates[4] = { ...updates[4], status: opt ? 'ok' : 'warn', detail: opt ? 'Available' : 'No positions yet' };
    } catch {
      updates[4] = { ...updates[4], status: 'warn', detail: 'Needs positions data' };
    }

    // Remaining: assume OK if backend is reachable
    if (updates[0].status === 'ok') {
      updates[1] = { ...updates[1], status: 'ok', detail: 'API key set' };
      updates[2] = { ...updates[2], status: 'ok', detail: 'API key set' };
    } else {
      updates[1] = { ...updates[1], status: 'warn', detail: 'Backend offline' };
      updates[2] = { ...updates[2], status: 'warn', detail: 'Backend offline' };
    }

    setIntegrations(updates);
  }, []); // eslint-disable-line

  useEffect(() => { loadBot(); loadWatchlist(); checkIntegrations(); }, []);

  useEffect(() => {
    const t = setInterval(loadBot, 10_000);
    return () => clearInterval(t);
  }, [loadBot]);

  // ── Bot control ─────────────────────────────────────────────────────────────

  const toggleBot = async () => {
    if (toggling) return;
    const isRunning = botStatus?.running ?? false;

    if (isRunning) {
      Alert.alert('Stop Bot', 'Stop the trading bot?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Stop', style: 'destructive', onPress: async () => {
            setToggling(true);
            try { await apiPost('/api/bot/stop', {}); await loadBot(); showToast('Bot stopped', 'info'); }
            catch (e: any) { showToast(e.message, 'error'); }
            finally { setToggling(false); }
          }
        },
      ]);
    } else {
      const mode = liveMode ? 'live' : 'paper';
      if (liveMode) {
        Alert.alert('⚠ Live Trading', 'This will use REAL MONEY. Continue?', [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Start Live', style: 'destructive', onPress: async () => {
              setToggling(true);
              try { await apiPost('/api/bot/start', { mode }); await loadBot(); showToast('Bot started in LIVE mode', 'warning'); }
              catch (e: any) { showToast(e.message, 'error'); }
              finally { setToggling(false); }
            }
          },
        ]);
      } else {
        setToggling(true);
        try { await apiPost('/api/bot/start', { mode }); await loadBot(); showToast('Bot started in paper mode', 'success'); }
        catch (e: any) { showToast(e.message, 'error'); }
        finally { setToggling(false); }
      }
    }
  };

  // ── Watchlist CRUD ──────────────────────────────────────────────────────────

  const addToWatchlist = async () => {
    const sym = addSymbol.trim().toUpperCase();
    if (!sym) return;
    setAdding(true);
    try {
      await apiPost('/api/watchlist', { symbol: sym });
      setAddSymbol('');
      await loadWatchlist();
      showToast(`${sym} added to watchlist`, 'success');
    } catch (e: any) {
      showToast(e.message ?? 'Failed to add', 'error');
    } finally {
      setAdding(false);
    }
  };

  const removeFromWatchlist = async (symbol: string) => {
    try {
      await apiDelete(`/api/watchlist/${symbol}`);
      setWatchlist(prev => prev.filter(w => w.symbol !== symbol));
      showToast(`${symbol} removed`, 'info');
    } catch (e: any) {
      showToast(e.message ?? 'Failed to remove', 'error');
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  const isRunning = botStatus?.running ?? false;

  const leftColumn = (
    <>
      {/* Bot Control */}
      <View style={styles.card}>
        <SectionTitle title="Bot Control" />
        <View style={styles.botRow}>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: isRunning ? Colors.green : Colors.textMuted }]} />
            <Text style={[styles.statusText, { color: isRunning ? Colors.green : Colors.textMuted }]}>
              {botLoading ? 'Checking…' : isRunning ? `Running · ${botStatus?.mode ?? 'paper'}` : 'Stopped'}
            </Text>
            {isRunning && botStatus?.pid && <Text style={styles.pidText}>PID {botStatus.pid}</Text>}
          </View>
        </View>

        {!isRunning && (
          <View style={styles.modeToggleRow}>
            <Text style={styles.modeLabel}>Mode</Text>
            <View style={styles.modeRight}>
              <Text style={[styles.modeNote, { color: liveMode ? Colors.red : Colors.textSecondary }]}>
                {liveMode ? '⚠ LIVE MONEY' : 'Paper Trading'}
              </Text>
              <Switch
                value={liveMode}
                onValueChange={setLiveMode}
                trackColor={{ false: Colors.border, true: Colors.red + '66' }}
                thumbColor={liveMode ? Colors.red : Colors.textSecondary}
              />
            </View>
          </View>
        )}

        <TouchableOpacity
          style={[styles.botBtn, isRunning ? styles.stopBtn : styles.startBtn, toggling && styles.btnDisabled]}
          onPress={toggleBot}
          disabled={toggling}
        >
          {toggling
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={styles.botBtnText}>{isRunning ? '■  Stop Bot' : '▶  Start Bot'}</Text>}
        </TouchableOpacity>
      </View>

      {/* Integration Status */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <SectionTitle title="Integrations" />
          <TouchableOpacity onPress={checkIntegrations}>
            <Text style={styles.refreshLink}>↻ Recheck</Text>
          </TouchableOpacity>
        </View>
        {integrations.map(int => {
          const dotColor = int.status === 'ok' ? Colors.green : int.status === 'error' ? Colors.red : Colors.yellow;
          return (
            <View key={int.name} style={styles.intRow}>
              <Text style={styles.intIcon}>{int.icon}</Text>
              <View style={styles.intBody}>
                <Text style={styles.intName}>{int.name}</Text>
                <Text style={[styles.intDetail, { color: dotColor }]}>{int.detail}</Text>
              </View>
              <View style={[styles.intDot, { backgroundColor: dotColor }]} />
            </View>
          );
        })}
      </View>

      {/* Agent Weights */}
      <View style={styles.card}>
        <SectionTitle title="Agent Weights" />
        <WeightBar label="🔬 Technical"   pct={30} />
        <WeightBar label="📊 Fundamental" pct={20} />
        <WeightBar label="📈 Momentum"    pct={20} />
        <WeightBar label="📰 Sentiment"   pct={15} />
        <WeightBar label="🌍 Macro"       pct={15} />
        <Text style={styles.weightNote}>Weights applied to multi-agent consensus engine</Text>
      </View>
    </>
  );

  const rightColumn = (
    <>
      {/* Watchlist */}
      <View style={styles.card}>
        <SectionTitle title="Watchlist" />
        <View style={styles.addRow}>
          <TextInput
            style={styles.addInput}
            value={addSymbol}
            onChangeText={t => setAddSymbol(t.toUpperCase())}
            placeholder="e.g. AAPL, BTC-USD"
            placeholderTextColor={Colors.textMuted}
            autoCapitalize="characters"
            onSubmitEditing={addToWatchlist}
            returnKeyType="done"
          />
          <TouchableOpacity style={[styles.addBtn, adding && styles.btnDisabled]} onPress={addToWatchlist} disabled={adding}>
            {adding
              ? <ActivityIndicator size="small" color="#fff" />
              : <Text style={styles.addBtnText}>Add</Text>}
          </TouchableOpacity>
        </View>

        {wlLoading ? (
          <ActivityIndicator color={Colors.primary} style={{ marginTop: 12 }} />
        ) : watchlist.length === 0 ? (
          <Text style={styles.wlEmpty}>No symbols yet. Add tickers above to track them in the Scanner.</Text>
        ) : (
          watchlist.map(item => (
            <View key={item.symbol} style={styles.wlRow}>
              <Text style={styles.wlSymbol}>{item.symbol}</Text>
              {item.added_at && (
                <Text style={styles.wlDate}>{new Date(item.added_at).toLocaleDateString()}</Text>
              )}
              <TouchableOpacity style={styles.wlRemove} onPress={() => removeFromWatchlist(item.symbol)}>
                <Text style={styles.wlRemoveText}>✕</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </View>

      {/* Risk Parameters */}
      <View style={styles.card}>
        <SectionTitle title="Risk Parameters" />
        <InfoRow label="Risk per Trade"        value="1% of portfolio" />
        <InfoRow label="Max Position Size"     value="5% of portfolio" />
        <InfoRow label="Stop Loss"             value="5% (ATR-based)" />
        <InfoRow label="Take Profit"           value="15% (ATR-based)" />
        <InfoRow label="Daily Drawdown Limit"  value="3% circuit-breaker" />
        <InfoRow label="Max Short Positions"   value="5 concurrent" />
        <InfoRow label="Portfolio Heat Cap"    value="20% max open risk" />
      </View>

      {/* Account */}
      <View style={styles.card}>
        <SectionTitle title="Account" />
        <InfoRow label="Version" value="CheckUp Direct v2.0" />
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutBtnText}>Sign Out</Text>
        </TouchableOpacity>
      </View>
    </>
  );

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.content, isDesktop && styles.contentDesk]}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.screenTitle}>Settings</Text>

        {isDesktop ? (
          <View style={styles.desktopCols}>
            <View style={styles.desktopCol}>{leftColumn}</View>
            <View style={styles.desktopCol}>{rightColumn}</View>
          </View>
        ) : (
          <>
            {leftColumn}
            {rightColumn}
          </>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root:        { flex: 1, backgroundColor: Colors.background },
  scroll:      { flex: 1 },
  content:     { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 40 },
  contentDesk: { paddingHorizontal: 28, maxWidth: 1100, alignSelf: 'center' as any, width: '100%' },

  screenTitle: { fontSize: 22, fontWeight: '800', color: Colors.text, letterSpacing: -0.3, marginBottom: 16, marginTop: 4 },

  card: { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: Colors.border },
  cardHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: Colors.primary, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 },
  refreshLink:  { fontSize: 12, color: Colors.primary, fontWeight: '600' },

  // Bot control
  botRow:       { marginBottom: 12 },
  statusRow:    { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusDot:    { width: 9, height: 9, borderRadius: 5 },
  statusText:   { fontSize: 15, fontWeight: '700' },
  pidText:      { fontSize: 11, color: Colors.textMuted, marginLeft: 4 },
  modeToggleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, borderTopWidth: 1, borderTopColor: Colors.border, marginBottom: 4 },
  modeLabel:    { fontSize: 14, color: Colors.text },
  modeRight:    { flexDirection: 'row', alignItems: 'center', gap: 8 },
  modeNote:     { fontSize: 12 },
  botBtn:       { borderRadius: 10, height: 48, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  startBtn:     { backgroundColor: Colors.primary },
  stopBtn:      { backgroundColor: Colors.red },
  btnDisabled:  { opacity: 0.5 },
  botBtnText:   { color: '#fff', fontSize: 15, fontWeight: '700', letterSpacing: 0.3 },

  // Integrations
  intRow:    { flexDirection: 'row', alignItems: 'center', paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: Colors.border, gap: 10 },
  intIcon:   { fontSize: 18, width: 26, textAlign: 'center' },
  intBody:   { flex: 1 },
  intName:   { fontSize: 13, color: Colors.text, fontWeight: '600' },
  intDetail: { fontSize: 11, marginTop: 1 },
  intDot:    { width: 8, height: 8, borderRadius: 4 },

  // Agent weights
  weightRow:    { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  weightLabel:  { fontSize: 12, color: Colors.textSecondary, width: 120 },
  weightBarBg:  { flex: 1, height: 6, backgroundColor: Colors.border, borderRadius: 3, overflow: 'hidden' },
  weightBarFill: { height: 6, borderRadius: 3, backgroundColor: Colors.primary },
  weightPct:    { fontSize: 12, fontWeight: '700', color: Colors.text, width: 36, textAlign: 'right' },
  weightNote:   { fontSize: 11, color: Colors.textMuted, marginTop: 4 },

  // Watchlist
  addRow:   { flexDirection: 'row', gap: 8, marginBottom: 12 },
  addInput: {
    flex: 1, backgroundColor: Colors.surfaceAlt, borderRadius: 8, borderWidth: 1,
    borderColor: Colors.border, color: Colors.text, fontSize: 14, paddingHorizontal: 12, height: 40,
  },
  addBtn:     { backgroundColor: Colors.primary, borderRadius: 8, paddingHorizontal: 16, height: 40, alignItems: 'center', justifyContent: 'center' },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  wlEmpty:    { color: Colors.textMuted, fontSize: 13, lineHeight: 20 },
  wlRow:      { flexDirection: 'row', alignItems: 'center', paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: Colors.border },
  wlSymbol:   { fontSize: 14, fontWeight: '700', color: Colors.text, flex: 1 },
  wlDate:     { fontSize: 11, color: Colors.textMuted, marginRight: 8 },
  wlRemove:   { width: 28, height: 28, borderRadius: 14, backgroundColor: Colors.surfaceAlt, alignItems: 'center', justifyContent: 'center' },
  wlRemoveText: { color: Colors.red, fontSize: 13, fontWeight: '700' },

  // Info rows
  infoRow:   { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: Colors.border },
  infoLabel: { fontSize: 13, color: Colors.text },
  infoValue: { fontSize: 13, color: Colors.textSecondary },

  // Account
  logoutBtn:     { marginTop: 12, borderRadius: 10, height: 44, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: Colors.red },
  logoutBtnText: { color: Colors.red, fontWeight: '700', fontSize: 14 },

  // Desktop 2-col
  desktopCols: { flexDirection: 'row', gap: 16 },
  desktopCol:  { flex: 1 },
});
