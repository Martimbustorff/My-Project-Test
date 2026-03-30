import { Tabs } from 'expo-router';
import React from 'react';
import { Text } from 'react-native';
import { Colors } from '@/constants/Colors';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: Colors.tabBar,
          borderTopColor: Colors.border,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.tabIconDefault,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen name="index"    options={{ title: 'Portfolio', tabBarIcon: ({ color }) => <TabBarEmoji emoji="💼" color={color} /> }} />
      <Tabs.Screen name="trades"   options={{ title: 'Scanner',   tabBarIcon: ({ color }) => <TabBarEmoji emoji="🔭" color={color} /> }} />
      <Tabs.Screen name="signals"  options={{ title: 'Signals',   tabBarIcon: ({ color }) => <TabBarEmoji emoji="⚡" color={color} /> }} />
      <Tabs.Screen name="backtest" options={{ title: 'Analysis',  tabBarIcon: ({ color }) => <TabBarEmoji emoji="🔬" color={color} /> }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings',  tabBarIcon: ({ color }) => <TabBarEmoji emoji="⚙️" color={color} /> }} />
    </Tabs>
  );
}

function TabBarEmoji({ emoji, color }: { emoji: string; color: string }) {
  return <Text style={{ fontSize: 22, opacity: color === Colors.primary ? 1 : 0.5 }}>{emoji}</Text>;
}
