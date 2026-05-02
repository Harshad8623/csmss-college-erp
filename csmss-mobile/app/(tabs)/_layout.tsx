// app/(tabs)/_layout.tsx — Bottom tab navigation (role-aware)
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/auth.store';

const ROLES_STUDENT = ['STUDENT', 'CR'];
const ROLES_STAFF   = ['TEACHER', 'CLASS_TEACHER', 'HOD', 'SUPER_ADMIN'];

export default function TabLayout() {
  const role = useAuthStore((s) => s.user?.role ?? '');

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0b1830',
          borderTopColor: 'rgba(59,130,246,0.15)',
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor:   '#3b82f6',
        tabBarInactiveTintColor: '#5a7499',
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="attendance"
        options={{
          title: 'Attendance',
          tabBarIcon: ({ color, size }) => <Ionicons name="checkmark-circle" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="marks"
        options={{
          title: 'Marks',
          tabBarIcon: ({ color, size }) => <Ionicons name="bar-chart" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="notices"
        options={{
          title: 'Notices',
          tabBarIcon: ({ color, size }) => <Ionicons name="notifications" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'More',
          tabBarIcon: ({ color, size }) => <Ionicons name="grid" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
