// app/(more)/_layout.tsx — Stack layout for all "more" screens
import { Stack } from 'expo-router';

export default function MoreStackLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#050d1a' } }}>
      <Stack.Screen name="mark-attendance" />
      <Stack.Screen name="upload-marks" />
      <Stack.Screen name="timetable" />
      <Stack.Screen name="assignments" />
      <Stack.Screen name="leaves" />
      <Stack.Screen name="grievances" />
      <Stack.Screen name="certificates" />
      <Stack.Screen name="profile" />
      <Stack.Screen name="sessions" />
    </Stack>
  );
}
