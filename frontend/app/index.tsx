// Gateway: decides whether to send the user to onboarding, language picker, or home.

import { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { ensureDeviceId, getLanguage, isOnboarded } from '../src/store';
import { colors } from '../src/theme';

export default function Index() {
  const router = useRouter();

  useEffect(() => {
    (async () => {
      await ensureDeviceId();
      const onboarded = await isOnboarded();
      if (!onboarded) {
        router.replace('/onboarding');
        return;
      }
      const lang = await getLanguage();
      if (!lang) {
        router.replace('/language?from=gateway');
        return;
      }
      router.replace('/home');
    })();
  }, [router]);

  return (
    <View style={styles.container}>
      <ActivityIndicator color={colors.primary} size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
