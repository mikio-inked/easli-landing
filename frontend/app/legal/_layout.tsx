// Stack layout for the public legal section. Inherits from root _layout
// (header hidden, slide-from-right animation). We keep this thin so the
// pages render the same way on web and on mobile.

import { Stack } from 'expo-router';
import { colors } from '../../src/theme';

export default function LegalLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: 'slide_from_right',
      }}
    />
  );
}
