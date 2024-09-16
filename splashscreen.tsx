import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';

type SplashScreenProps = {
  onFinish: () => void;
};

const SplashScreen: React.FC<SplashScreenProps> = ({ onFinish }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onFinish();
    }, 2000); // 2 seconds duration

    return () => clearTimeout(timer);
  }, [onFinish]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>CheckUp Direct</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0057A6', // Superman Blue
  },
  title: {
    fontSize: 36,
    color: '#FFFFFF', // White color
    fontFamily: 'Arial',
    fontWeight: 'bold',
  },
});

export default SplashScreen;
