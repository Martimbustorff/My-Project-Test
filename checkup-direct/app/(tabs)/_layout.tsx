import { Tabs, useRouter, usePathname } from 'expo-router';
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, useWindowDimensions } from 'react-native';
import { Colors } from '@/constants/Colors';
import { MarketBadge } from '@/components/MarketBadge';

const NAV_ITEMS = [
  { route: '/',          label: 'Portfolio', emoji: '💼' },
  { route: '/trades',    label: 'Scanner',   emoji: '🔭' },
  { route: '/signals',   label: 'Signals',   emoji: '⚡' },
  { route: '/backtest',  label: 'Analysis',  emoji: '🔬' },
  { route: '/ask',       label: 'Ask',       emoji: '🧠' },
  { route: '/explore',   label: 'Market',    emoji: '🌍' },
  { route: '/settings',  label: 'Settings',  emoji: '⚙️' },
];

function SidebarNav() {
  const router = useRouter();
  const pathname = usePathname();

  function isActive(route: string) {
    if (route === '/') return pathname === '/' || pathname === '/index';
    return pathname.includes(route.replace('/', ''));
  }

  return (
    <View style={styles.sidebar}>
      {/* Logo */}
      <View style={styles.logoRow}>
        <View style={styles.logoCircle}>
          <Text style={styles.logoText}>CD</Text>
        </View>
        <Text style={styles.logoLabel}>CheckUp Direct</Text>
      </View>

      <View style={styles.divider} />

      {/* Nav items */}
      <View style={styles.navItems}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.route);
          return (
            <TouchableOpacity
              key={item.route}
              style={[styles.navItem, active && styles.navItemActive]}
              onPress={() => router.push(item.route as any)}
              activeOpacity={0.7}
            >
              <Text style={styles.navEmoji}>{item.emoji}</Text>
              <Text style={[styles.navLabel, active && styles.navLabelActive]}>
                {item.label}
              </Text>
              {active && <View style={styles.activeIndicator} />}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Market badge at bottom */}
      <View style={styles.sidebarBottom}>
        <View style={styles.divider} />
        <View style={styles.marketBadgeContainer}>
          <MarketBadge />
        </View>
      </View>
    </View>
  );
}

function TabBarEmoji({ emoji, color }: { emoji: string; color: string }) {
  return <Text style={{ fontSize: 22, opacity: color === Colors.primary ? 1 : 0.5 }}>{emoji}</Text>;
}

export default function TabLayout() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;

  if (isDesktop) {
    return (
      <View style={styles.desktopContainer}>
        <SidebarNav />
        <View style={styles.desktopContent}>
          <Tabs
            screenOptions={{
              headerShown: false,
              tabBarStyle: { display: 'none' },
            }}
          >
            <Tabs.Screen name="index"    options={{ title: 'Portfolio' }} />
            <Tabs.Screen name="trades"   options={{ title: 'Scanner' }} />
            <Tabs.Screen name="signals"  options={{ title: 'Signals' }} />
            <Tabs.Screen name="backtest" options={{ title: 'Analysis' }} />
            <Tabs.Screen name="ask"      options={{ title: 'Ask' }} />
            <Tabs.Screen name="explore"  options={{ title: 'Market' }} />
            <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
          </Tabs>
        </View>
      </View>
    );
  }

  // Mobile: standard bottom tab bar
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
      <Tabs.Screen name="ask"      options={{ title: 'Ask',       tabBarIcon: ({ color }) => <TabBarEmoji emoji="🧠" color={color} /> }} />
      <Tabs.Screen name="explore"  options={{ title: 'Market',    tabBarIcon: ({ color }) => <TabBarEmoji emoji="🌍" color={color} /> }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings',  tabBarIcon: ({ color }) => <TabBarEmoji emoji="⚙️" color={color} /> }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  // Desktop layout
  desktopContainer: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: Colors.background,
  },
  desktopContent: {
    flex: 1,
    // Compensate for fixed-position sidebar on web
    ...(Platform.OS === 'web' ? { marginLeft: 200 } : {}),
  },

  // Sidebar
  sidebar: {
    width: 200,
    backgroundColor: Colors.sidebar,
    borderRightWidth: 1,
    borderRightColor: Colors.border,
    paddingTop: Platform.OS === 'web' ? 0 : 44, // safe area on native
    ...(Platform.OS === 'web' ? {
      position: 'fixed' as any,
      top: 0,
      left: 0,
      bottom: 0,
      zIndex: 100,
    } : {}),
  },

  // Logo area
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  logoCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  logoLabel: {
    color: Colors.text,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.3,
    flex: 1,
  },

  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginHorizontal: 12,
    marginBottom: 8,
  },

  // Nav items
  navItems: {
    flex: 1,
    paddingTop: 4,
  },
  navItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 11,
    marginHorizontal: 8,
    marginVertical: 2,
    borderRadius: 8,
    position: 'relative',
  },
  navItemActive: {
    backgroundColor: Colors.surfaceAlt,
  },
  navEmoji: {
    fontSize: 16,
    width: 22,
    textAlign: 'center',
  },
  navLabel: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
  navLabelActive: {
    color: Colors.text,
    fontWeight: '700',
  },
  activeIndicator: {
    position: 'absolute',
    left: 0,
    top: 6,
    bottom: 6,
    width: 3,
    borderRadius: 2,
    backgroundColor: Colors.primary,
  },

  // Sidebar bottom
  sidebarBottom: {
    paddingBottom: 20,
  },
  marketBadgeContainer: {
    paddingHorizontal: 16,
    paddingTop: 12,
  },
});
