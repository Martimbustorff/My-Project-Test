import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '@/constants/Colors';

function getMarketStatus(): { label: string; color: string; dot: string } {
  const now = new Date();
  // Convert to ET (UTC-5 or UTC-4)
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  const et = new Date(utc + -4 * 3600000); // approximate EDT
  const h = et.getHours();
  const m = et.getMinutes();
  const mins = h * 60 + m;
  const day = et.getDay(); // 0=Sun, 6=Sat

  if (day === 0 || day === 6) return { label: 'WEEKEND', color: Colors.textMuted, dot: '⬤' };
  if (mins >= 570 && mins < 930) return { label: 'MARKET OPEN', color: Colors.green, dot: '⬤' }; // 9:30-15:30
  if (mins >= 480 && mins < 570) return { label: 'PRE-MARKET', color: Colors.yellow, dot: '⬤' }; // 8:00-9:30
  if (mins >= 960 && mins < 1200) return { label: 'AFTER-HOURS', color: Colors.orange, dot: '⬤' }; // 16:00-20:00
  return { label: 'MARKET CLOSED', color: Colors.textMuted, dot: '⬤' };
}

export function MarketBadge() {
  const [status, setStatus] = useState(getMarketStatus());
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setStatus(getMarketStatus());
      setTime(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const timeStr = time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });

  return (
    <View style={styles.container}>
      <Text style={[styles.dot, { color: status.color }]}>{status.dot}</Text>
      <Text style={[styles.label, { color: status.color }]}>{status.label}</Text>
      <Text style={styles.time}>{timeStr}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { fontSize: 8 },
  label: { fontSize: 11, fontWeight: '700', letterSpacing: 0.8 },
  time: { fontSize: 11, color: Colors.textMuted, letterSpacing: 0.5 },
});
