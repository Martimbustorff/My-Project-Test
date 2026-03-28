import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  Switch, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors } from '@/constants/Colors';
import { apiGet, apiPost } from '@/constants/Api';
import { useAuth } from '@/hooks/useAuth';

interface BotStatus {
  running: boolean;
  mode: string | null;
  pid: number | null;
}

function SectionHeader({ title }: { title: string }) {
  return <Text style={styles.sectionHeader}>{title}</Text>;
}

function SettingRow({ label, value, onPress, danger }: { label: string; value: string; onPress?: () => void; danger?: boolean }) {
  return (
    <TouchableOpacity style={styles.settingRow} onPress={onPress} disabled={!onPress}>
      <Text style={[styles.settingLabel, danger && { color: Colors.red }]}>{label}</Text>
      <Text style={[styles.settingValue, danger && { color: Colors.red }]}>{value}</Text>
    </TouchableOpacity>
  );
}

export default function SettingsScreen() {
  const { logout } = useAuth();
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading]     = useState(true);
  const [toggling, setToggling]   = useState(false);
  const [liveMode, setLiveMode]   = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const s = await apiGet<BotStatus>('/api/bot/status');
      setBotStatus(s);
    } catch { /* API not running yet */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);
  useEffect(() => {
    const i = setInterval(loadStatus, 10_000);
    return () => clearInterval(i);
  }, [loadStatus]);

  const toggleBot = async () => {
    if (toggling) return;

    if (botStatus?.running) {
      Alert.alert('Stop Bot', 'Stop the trading bot?', [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Stop', style: 'destructive', onPress: async () => {
            setToggling(true);
            try {
              await apiPost('/api/bot/stop', {});
              await loadStatus();
            } catch (e: any) { Alert.alert('Error', e.message); }
            finally { setToggling(false); }
          }
        }
      ]);
    } else {
      const mode = liveMode ? 'live' : 'paper';
      if (liveMode) {
        Alert.alert('⚠ Live Trading', 'This will use REAL MONEY. Are you sure?', [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Start Live', style: 'destructive', onPress: async () => {
              setToggling(true);
              try { await apiPost('/api/bot/start', { mode }); await loadStatus(); }
              catch (e: any) { Alert.alert('Error', e.message); }
              finally { setToggling(false); }
            }
          }
        ]);
      } else {
        setToggling(true);
        try { await apiPost('/api/bot/start', { mode }); await loadStatus(); }
        catch (e: any) { Alert.alert('Error', e.message); }
        finally { setToggling(false); }
      }
    }
  };

  const isRunning = botStatus?.running ?? false;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.headerTitle}>Settings</Text>

        {/* Bot Control */}
        <View style={styles.card}>
          <SectionHeader title="Bot Control" />
          <View style={styles.botStatusRow}>
            <View>
              <Text style={styles.botStatusLabel}>Status</Text>
              <View style={styles.botStatusBadge}>
                <View style={[styles.statusDot, { backgroundColor: isRunning ? Colors.green : Colors.textMuted }]} />
                <Text style={[styles.statusText, { color: isRunning ? Colors.green : Colors.textMuted }]}>
                  {loading ? 'Checking…' : isRunning ? `Running (${botStatus?.mode ?? 'paper'})` : 'Stopped'}
                </Text>
              </View>
              {isRunning && botStatus?.pid && (
                <Text style={styles.pidText}>PID: {botStatus.pid}</Text>
              )}
            </View>
          </View>

          {!isRunning && (
            <View style={styles.modeRow}>
              <Text style={styles.modeLabel}>Live Trading</Text>
              <View style={styles.modeRight}>
                <Text style={styles.modeNote}>{liveMode ? '⚠ Real Money' : 'Paper Mode'}</Text>
                <Switch
                  value={liveMode}
                  onValueChange={setLiveMode}
                  trackColor={{ false: Colors.border, true: Colors.red + '88' }}
                  thumbColor={liveMode ? Colors.red : Colors.textSecondary}
                />
              </View>
            </View>
          )}

          <TouchableOpacity
            style={[styles.botButton, isRunning ? styles.stopButton : styles.startButton, toggling && styles.disabled]}
            onPress={toggleBot}
            disabled={toggling}
          >
            {toggling
              ? <ActivityIndicator color="#fff" size="small" />
              : <Text style={styles.botButtonText}>{isRunning ? '■ Stop Bot' : '▶ Start Bot'}</Text>}
          </TouchableOpacity>
        </View>

        {/* API Info */}
        <View style={styles.card}>
          <SectionHeader title="Configuration" />
          <SettingRow label="API Endpoint" value="localhost:8000" />
          <SettingRow label="Trading Mode" value={botStatus?.mode ?? 'paper'} />
          <SettingRow label="Signal Scan" value="Every 1 minute" />
          <SettingRow label="News Refresh" value="Every 60 minutes" />
          <SettingRow label="Sentiment Model" value="ProsusAI/finbert" />
        </View>

        {/* Risk */}
        <View style={styles.card}>
          <SectionHeader title="Risk Parameters" />
          <SettingRow label="Risk per Trade" value="1% of portfolio" />
          <SettingRow label="Max Position Size" value="5% of portfolio" />
          <SettingRow label="Stop Loss" value="5% (ATR-based)" />
          <SettingRow label="Take Profit" value="15% (ATR-based)" />
          <SettingRow label="Daily Drawdown Limit" value="3% circuit-breaker" />
          <SettingRow label="Max Short Positions" value="5 concurrent" />
          <SettingRow label="Portfolio Heat Cap" value="20% max open risk" />
        </View>

        {/* Signal Weights */}
        <View style={styles.card}>
          <SectionHeader title="Signal Weights" />
          <SettingRow label="Technical Analysis" value="35%" />
          <SettingRow label="News Sentiment" value="30%" />
          <SettingRow label="Momentum" value="20%" />
          <SettingRow label="Fundamentals" value="15%" />
        </View>

        {/* Account */}
        <View style={styles.card}>
          <SectionHeader title="Account" />
          <SettingRow label="Sign Out" value="→" onPress={logout} danger />
        </View>

        <Text style={styles.footer}>CheckUp Direct Trading Platform v1.0</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: 16, paddingBottom: 40 },
  headerTitle: { fontSize: 26, fontWeight: 'bold', color: Colors.text, marginBottom: 20 },
  card: { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: Colors.border },
  sectionHeader: { fontSize: 11, fontWeight: '700', color: Colors.primary, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 },
  botStatusRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 },
  botStatusLabel: { fontSize: 12, color: Colors.textSecondary, marginBottom: 6 },
  botStatusBadge: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusText: { fontSize: 15, fontWeight: '600' },
  pidText: { fontSize: 11, color: Colors.textMuted, marginTop: 4 },
  modeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, borderTopWidth: 1, borderTopColor: Colors.border },
  modeLabel: { fontSize: 15, color: Colors.text },
  modeRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  modeNote: { fontSize: 12, color: Colors.textSecondary },
  botButton: { borderRadius: 12, height: 50, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  startButton: { backgroundColor: Colors.primary },
  stopButton: { backgroundColor: Colors.red },
  disabled: { opacity: 0.6 },
  botButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: Colors.border },
  settingLabel: { fontSize: 14, color: Colors.text },
  settingValue: { fontSize: 14, color: Colors.textSecondary },
  footer: { color: Colors.textMuted, textAlign: 'center', fontSize: 12, marginTop: 8 },
});
