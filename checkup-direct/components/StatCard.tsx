import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '@/constants/Colors';

interface Props {
  label: string;
  value: string;
  subValue?: string;
  valueColor?: string;
  flex?: number;
}

export function StatCard({ label, value, subValue, valueColor, flex = 1 }: Props) {
  return (
    <View style={[styles.card, { flex }]}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, valueColor ? { color: valueColor } : {}]}>{value}</Text>
      {subValue ? <Text style={styles.subValue}>{subValue}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  label: { fontSize: 11, color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 },
  value: { fontSize: 20, fontWeight: '700', color: Colors.text },
  subValue: { fontSize: 12, color: Colors.textSecondary, marginTop: 3 },
});
