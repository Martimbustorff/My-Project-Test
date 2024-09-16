import React, { useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import AppNavigator from './src/navigation/AppNavigator';
import SplashScreen from './src/components/SplashScreen';

const App = () => {
  const [isSplashVisible, setSplashVisible] = useState(true);

  // Show splash for 2 seconds, then switch to main navigation
  return isSplashVisible ? (
    <SplashScreen onFinish={() => setSplashVisible(false)} />
  ) : (
    <NavigationContainer>
      <AppNavigator />
    </NavigationContainer>
  );
};

export default App;
