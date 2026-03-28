import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  TextInput, ActivityIndicator, Alert, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet, apiPost } from '@/constants/Api';

interface BacktestResult {
  id: string;
  symbols: string | string[];
  start_date: string;
  end_date: string;
  total_return: number;
  ann_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  status: string;
  created_at: string;
}

function pctFmt(v: number) { return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%`; }
function pnlColor(v: number) { return v >= 0 ? Colors.green : Colors.red; }

function ResultCard({ result }: { result: BacktestResult }) {
  const symbols = typeof result.symbols === 'string'
    ? JSON.parse(result.symbols)
    : result.symbols;
  return (
    <View style={styles.resultCard}>
      <View style={styles.resultHeader}>
        <Text style={styles.resultSymbols}>{symbols.slice(0, 4).join(', ')}{symbols.length > 4 ? ` +${symbols.length - 4}` : ''}</Text>
        <Text style={styles.resultDate}>{result.start_date} → {result.end_date}</Text>
      </View>
      <View style={styles.resultGrid}>
        <View style={styles.resultMetric}>
          <Text style={[styles.metricValue, { color: pnlColor(result.total_return) }]}>{pctFmt(result.total_return)}</Text>
          <Text style={styles.metricLabel}>Return</Text>
        </View>
        <View style={styles.resultMetric}>
          <Text style={[styles.metricValue, { color: result.sharpe >= 1 ? Colors.green : Colors.yellow }]}>{result.sharpe?.toFixed(2) ?? '—'}</Text>
          <Text style={styles.metricLabel}>Sharpe</Text>
        </View>
        <View style={styles.resultMetric}>
          <Text style={[styles.metricValue, { color: Colors.red }]}>{pctFmt(result.max_drawdown)}</Text>
          <Text style={styles.metricLabel}>Max DD</Text>
        </View>
        <View style={styles.resultMetric}>
          <Text style={styles.metricValue}>{((result.win_rate ?? 0) * 100).toFixed(0)}%</Text>
          <Text style={styles.metricLabel}>Win Rate</Text>
        </View>
        <View style={styles.resultMetric}>
          <Text style={styles.metricValue}>{result.profit_factor?.toFixed(2) ?? '—'}</Text>
          <Text style={styles.metricLabel}>Profit F.</Text>
        </View>
        <View style={styles.resultMetric}>
          <Text style={styles.metricValue}>{result.total_trades ?? 0}</Text>
          <Text style={styles.metricLabel}>Trades</Text>
        </View>
      </View>
    </View>
  );
}

const PRESET_SYMBOLS = ['AAPL,MSFT,NVDA', 'AAPL,MSFT,GOOGL,AMZN', 'JPM,GS,V,MA', 'XOM,CVX,NEE'];

export default function BacktestScreen() {
  const [symbols, setSymbols]     = useState('AAPL,MSFT,NVDA');
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate]     = useState('2024-01-01');
  const [capital, setCapital]     = useState('100000');
  const [running, setRunning]     = useState(false);
  const [jobId, setJobId]         = useState<string | null>(null);
  const [results, setResults]     = useState<BacktestResult[]>([]);
  const [loadingResults, setLoadingResults] = useState(true);
  const [error, setError]         = useState<string | null>(null);

  const loadResults = useCallback(async () => {
    try {
      const data = await apiGet<BacktestResult[]>('/api/backtest/results');
      setResults(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingResults(false);
    }
  }, []);

  useEffect(() => { loadResults(); }, [loadResults]);

  // Poll job status while running
  useEffect(() => {
    if (!jobId || !running) return;
    const poll = setInterval(async () => {
      try {
        const status = await apiGet<{ status: string; error?: string }>(`/api/backtest/status/${jobId}`);
        if (status.status === 'completed') {
          setRunning(false);
          setJobId(null);
          loadResults();
          clearInterval(poll);
        } else if (status.status === 'failed') {
          setRunning(false);
          setJobId(null);
          Alert.alert('Backtest Failed', status.error || 'Unknown error');
          clearInterval(poll);
        }
      } catch { clearInterval(poll); }
    }, 3000);
    return () => clearInterval(poll);
  }, [jobId, running, loadResults]);

  const runBacktest = async () => {
    const syms = symbols.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    if (syms.length === 0) { Alert.alert('Error', 'Enter at least one symbol.'); return; }
    setRunning(true);
    setError(null);
    try {
      const resp = await apiPost<{ job_id: string }>('/api/backtest/run', {
        symbols: syms, start_date: startDate, end_date: endDate,
        initial_capital: parseFloat(capital) || 100000,
      });
      setJobId(resp.job_id);
    } catch (e: any) {
      setRunning(false);
      Alert.alert('Error', e.message);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.headerTitle}>Backtest</Text>

        {/* Config form */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Configuration</Text>

          <Text style={styles.label}>Symbols (comma-separated)</Text>
          <TextInput style={styles.input} value={symbols} onChangeText={setSymbols} autoCapitalize="characters" placeholder="AAPL,MSFT,NVDA" placeholderTextColor={Colors.textMuted} />

          {/* Presets */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.presetScroll}>
            {PRESET_SYMBOLS.map(p => (
              <TouchableOpacity key={p} style={[styles.preset, symbols === p && styles.presetActive]} onPress={() => setSymbols(p)}>
                <Text style={[styles.presetText, symbols === p && styles.presetTextActive]}>{p}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <View style={styles.dateRow}>
            <View style={styles.dateField}>
              <Text style={styles.label}>Start Date</Text>
              <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textMuted} />
            </View>
            <View style={{ width: 12 }} />
            <View style={styles.dateField}>
              <Text style={styles.label}>End Date</Text>
              <TextInput style={styles.input} value={endDate} onChangeText={setEndDate} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textMuted} />
            </View>
          </View>

          <Text style={styles.label}>Initial Capital ($)</Text>
          <TextInput style={styles.input} value={capital} onChangeText={setCapital} keyboardType="numeric" placeholder="100000" placeholderTextColor={Colors.textMuted} />

          <TouchableOpacity style={[styles.runButton, running && styles.runButtonDisabled]} onPress={runBacktest} disabled={running}>
            {running
              ? <><ActivityIndicator color="#fff" size="small" /><Text style={styles.runButtonText}> Running…</Text></>
              : <Text style={styles.runButtonText}>▶ Run Backtest</Text>}
          </TouchableOpacity>
        </View>

        {/* Results */}
        <Text style={styles.sectionTitle}>Past Results</Text>
        {loadingResults
          ? <ActivityIndicator color={Colors.primary} />
          : results.length === 0
            ? <Text style={styles.emptyText}>No completed backtests yet.</Text>
            : results.map(r => <ResultCard key={r.id} result={r} />)}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: 16, paddingBottom: 40 },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text, marginBottom: 16 },
  card: { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: Colors.border },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 14 },
  label: { fontSize: 12, color: Colors.textSecondary, marginBottom: 6, marginTop: 10 },
  input: { backgroundColor: Colors.surfaceAlt, borderWidth: 1, borderColor: Colors.border, borderRadius: 10, height: 44, paddingHorizontal: 12, color: Colors.text, fontSize: 14 },
  presetScroll: { marginTop: 8, marginBottom: 4 },
  preset: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, backgroundColor: Colors.surfaceAlt, borderWidth: 1, borderColor: Colors.border, marginRight: 8 },
  presetActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  presetText: { fontSize: 12, color: Colors.textSecondary },
  presetTextActive: { color: '#fff', fontWeight: '600' },
  dateRow: { flexDirection: 'row' },
  dateField: { flex: 1 },
  runButton: { backgroundColor: Colors.primary, borderRadius: 12, height: 50, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', marginTop: 20 },
  runButtonDisabled: { opacity: 0.6 },
  runButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  resultCard: { backgroundColor: Colors.surface, borderRadius: 14, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: Colors.border },
  resultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  resultSymbols: { fontSize: 15, fontWeight: '700', color: Colors.text },
  resultDate: { fontSize: 11, color: Colors.textSecondary },
  resultGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  resultMetric: { width: '30%', backgroundColor: Colors.surfaceAlt, borderRadius: 8, padding: 10, alignItems: 'center' },
  metricValue: { fontSize: 16, fontWeight: '700', color: Colors.text },
  metricLabel: { fontSize: 10, color: Colors.textSecondary, marginTop: 3, textTransform: 'uppercase' },
  emptyText: { color: Colors.textSecondary, textAlign: 'center', paddingTop: 20 },
});
