import AddRounded from '@mui/icons-material/AddRounded'
import ChatBubbleOutlineRounded from '@mui/icons-material/ChatBubbleOutlineRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import ForumRounded from '@mui/icons-material/ForumRounded'
import ScheduleRounded from '@mui/icons-material/ScheduleRounded'
import SettingsRounded from '@mui/icons-material/SettingsRounded'
import {
  Alert,
  AppBar,
  Box,
  Button,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from './api'
import { Brand } from './components/Brand'
import type { Conversation } from './types'
import { AutomationsView } from './views/AutomationsView'
import { ChatView } from './views/ChatView'
import { SettingsView } from './views/SettingsView'

const drawerWidth = 286
type View = 'chat' | 'automations' | 'settings'

interface NavigationProps {
  view: View
  conversations: Conversation[]
  activeConversationId: string | null
  onNavigate: (view: View) => void
  onSelectConversation: (id: string) => void
  onCreateConversation: () => void
  onDeleteConversation: (id: string) => void
}

export function Navigation({
  view,
  conversations,
  activeConversationId,
  onNavigate,
  onSelectConversation,
  onCreateConversation,
  onDeleteConversation,
}: NavigationProps) {
  return (
    <Box className="drawer-content">
      <Box px={2.2} pt={2.5} pb={2}><Brand /></Box>
      <Box px={1.4}>
        <Button fullWidth variant="contained" startIcon={<AddRounded />} onClick={onCreateConversation}>
          New conversation
        </Button>
      </Box>
      <List sx={{ px: 1.2, mt: 1.2 }}>
        <ListItem disablePadding>
          <ListItemButton selected={view === 'chat'} onClick={() => onNavigate('chat')}>
            <ListItemIcon><ChatBubbleOutlineRounded /></ListItemIcon>
            <ListItemText primary="Chat" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton selected={view === 'automations'} onClick={() => onNavigate('automations')}>
            <ListItemIcon><ScheduleRounded /></ListItemIcon>
            <ListItemText primary="Automations" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton selected={view === 'settings'} onClick={() => onNavigate('settings')}>
            <ListItemIcon><SettingsRounded /></ListItemIcon>
            <ListItemText primary="Settings" />
          </ListItemButton>
        </ListItem>
      </List>
      <Divider sx={{ mx: 2, my: 1 }} />
      <Typography variant="overline" color="text.secondary" px={2.2}>Recent</Typography>
      <List dense sx={{ px: 1.2, overflowY: 'auto' }}>
        {conversations.map((conversation) => (
          <ListItem
            key={conversation.id}
            disablePadding
            secondaryAction={
              <IconButton
                size="small"
                aria-label={`Delete ${conversation.title}`}
                onClick={() => onDeleteConversation(conversation.id)}
              >
                <DeleteOutlineRounded fontSize="small" />
              </IconButton>
            }
          >
            <ListItemButton
              selected={view === 'chat' && activeConversationId === conversation.id}
              onClick={() => onSelectConversation(conversation.id)}
            >
              <ListItemText primary={conversation.title} primaryTypographyProps={{ noWrap: true }} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Box mt="auto" px={2.2} py={2}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Box className="status-dot" />
          <Typography variant="caption" color="text.secondary">Local instance</Typography>
        </Stack>
      </Box>
    </Box>
  )
}

export default function App() {
  const theme = useTheme()
  const compact = useMediaQuery(theme.breakpoints.down('md'))
  const queryClient = useQueryClient()
  const [view, setView] = useState<View>('chat')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const capabilities = useQuery({
    queryKey: ['capabilities'],
    queryFn: api.capabilities,
    refetchInterval: 15_000,
  })
  const conversations = useQuery({ queryKey: ['conversations'], queryFn: api.conversations })
  const createConversation = useMutation({
    mutationFn: () => api.createConversation(),
    onSuccess: (conversation) => {
      setActiveConversationId(conversation.id)
      setView('chat')
      setMobileOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })

  useEffect(() => {
    if (!activeConversationId && conversations.data?.length) {
      setActiveConversationId(conversations.data[0].id)
    }
  }, [activeConversationId, conversations.data])

  const activeConversation =
    conversations.data?.find((conversation) => conversation.id === activeConversationId) ?? null

  const navigate = (next: View) => {
    setView(next)
    setMobileOpen(false)
  }

  const navigation = (
    <Navigation
      view={view}
      conversations={conversations.data ?? []}
      activeConversationId={activeConversationId}
      onNavigate={navigate}
      onSelectConversation={(id) => {
        setActiveConversationId(id)
        navigate('chat')
      }}
      onCreateConversation={() => createConversation.mutate()}
      onDeleteConversation={(id) => {
        void api.deleteConversation(id).then(() => {
          if (activeConversationId === id) setActiveConversationId(null)
          void queryClient.invalidateQueries({ queryKey: ['conversations'] })
        })
      }}
    />
  )

  if (capabilities.isLoading) {
    return <Box className="loading-screen"><Brand /><CircularProgress size={24} /></Box>
  }
  if (capabilities.error || !capabilities.data) {
    return <Box className="loading-screen"><Alert severity="error">Unable to load backend capabilities.</Alert></Box>
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {compact && (
        <AppBar position="fixed" color="transparent" elevation={0} className="mobile-bar">
          <Toolbar>
            <IconButton aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
              <ForumRounded />
            </IconButton>
            <Brand />
          </Toolbar>
        </AppBar>
      )}
      <Drawer
        variant={compact ? 'temporary' : 'permanent'}
        open={compact ? mobileOpen : true}
        onClose={() => setMobileOpen(false)}
        sx={{ '& .MuiDrawer-paper': { width: drawerWidth } }}
      >
        {navigation}
      </Drawer>
      <Box
        component="main"
        sx={{ flex: 1, minWidth: 0, ml: compact ? 0 : `${drawerWidth}px`, pt: compact ? 8 : 0 }}
      >
        {view === 'chat' && (
          <ChatView capabilities={capabilities.data} conversation={activeConversation} />
        )}
        {view === 'automations' && <AutomationsView capabilities={capabilities.data} />}
        {view === 'settings' && <SettingsView capabilities={capabilities.data} />}
      </Box>
    </Box>
  )
}
