/**
 * Toast — in-app notification system.
 * Usage: import { showToast } from '@/components/Toast';
 *        showToast({ message: 'Strong BUY on AAPL!', type: 'success' });
 *
 * Wrap app root with <ToastProvider /> to enable.
 */
import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { View, Text, StyleSheet, Animated, TouchableOpacity, Platform } from 'react-native';
import { Colors } from '@/constants/Colors';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastMessage {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  show: (msg: Omit<ToastMessage, 'id'>) => void;
}

const ToastContext = createContext<ToastContextType>({ show: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

// Global ref for imperative usage
let _showToast: ((msg: Omit<ToastMessage, 'id'>) => void) | null = null;
export function showToast(msg: Omit<ToastMessage, 'id'>) {
  _showToast?.(msg);
}

function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: () => void }) {
  const opacity = useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    Animated.sequence([
      Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      Animated.delay(toast.duration || 3500),
      Animated.timing(opacity, { toValue: 0, duration: 300, useNativeDriver: true }),
    ]).start(onDismiss);
  }, []);

  const colors: Record<ToastType, string> = {
    success: Colors.green,
    error: Colors.red,
    warning: Colors.yellow,
    info: Colors.blue,
  };
  const icons: Record<ToastType, string> = {
    success: '✓', error: '✕', warning: '⚠', info: 'ℹ',
  };

  const c = colors[toast.type];

  return (
    <Animated.View style={[styles.toast, { opacity, borderLeftColor: c, borderLeftWidth: 3 }]}>
      <Text style={[styles.icon, { color: c }]}>{icons[toast.type]}</Text>
      <Text style={styles.msg} numberOfLines={2}>{toast.message}</Text>
      <TouchableOpacity onPress={onDismiss} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Text style={styles.close}>✕</Text>
      </TouchableOpacity>
    </Animated.View>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const show = useCallback((msg: Omit<ToastMessage, 'id'>) => {
    const id = Date.now().toString();
    setToasts(prev => [...prev.slice(-3), { ...msg, id }]); // max 4 toasts
  }, []);

  _showToast = show;

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <View style={styles.container} pointerEvents="box-none">
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </View>
    </ToastContext.Provider>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 60,
    right: 16,
    zIndex: 9999,
    gap: 8,
    maxWidth: 360,
    ...(Platform.OS === 'web' ? { position: 'fixed' as any } : {}),
  },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    padding: 12,
    paddingLeft: 14,
    gap: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
  },
  icon: { fontSize: 14, fontWeight: '700', width: 16, textAlign: 'center' },
  msg: { flex: 1, color: Colors.text, fontSize: 13, lineHeight: 18 },
  close: { color: Colors.textMuted, fontSize: 12 },
});
