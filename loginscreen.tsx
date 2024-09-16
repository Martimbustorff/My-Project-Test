import React from 'react';
import { View, Text, TextInput, Button, StyleSheet, TouchableOpacity } from 'react-native';

const LoginScreen = ({ navigation }) => {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Login</Text>
      <TextInput
        style={styles.input}
        placeholder="Email"
        placeholderTextColor="#ccc"
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        secureTextEntry
        placeholderTextColor="#ccc"
      />
      <TouchableOpacity style={styles.button}>
        <Text style={styles.buttonText}>Login</Text>
      </TouchableOpacity>
      <Text
        style={styles.link}
        onPress={() => navigation.navigate('Signup')}
      >
        Don't have an account? Sign up
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
    backgroundColor: '#0057A6', // Superman Blue background
  },
  title: {
    fontSize: 24,
    color: '#FFFFFF', // White color
    textAlign: 'center',
    marginBottom: 20,
    fontWeight: 'bold',
  },
  input: {
    height: 48,
    borderColor: '#FFFFFF',
    borderWidth: 1,
    borderRadius: 5,
    marginBottom: 20,
    paddingLeft: 10,
    color: '#FFFFFF',
  },
  button: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderRadius: 5,
    alignItems: 'center',
  },
  buttonText: {
    color: '#0057A6',
    fontSize: 16,
    fontWeight: 'bold',
  },
  link: {
    color: '#FFFFFF',
    textAlign: 'center',
    marginTop: 10,
    textDecorationLine: 'underline',
  },
});

export default LoginScreen;
