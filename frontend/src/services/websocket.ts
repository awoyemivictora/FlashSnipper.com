// services/websocket.ts
// Define event data interfaces
interface WebSocketEventData {
  event?: string;
  type?: string;
  launch_id?: string;
  launchId?: string;
  data?: any;
  message?: string;
  status?: string;
  progress?: number;
  error?: string;
  timestamp?: string;
  [key: string]: any;
}


class LaunchWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private listeners: Map<string, Function[]> = new Map();
  private launchId: string | null = null;

  connect(launchId: string) {
    this.launchId = launchId;
    // const wsUrl = `ws://${window.location.host}/ws/launch/${launchId}`;
    
    const baseUrl = process.env.VITE_WS_URL || 'ws://localhost:8000';

    const wsUrl = `${baseUrl}/ws/launch/${launchId}`;
  
    console.log('Connecting to WebSocket:', wsUrl);
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected for launch:', launchId);
      this.reconnectAttempts = 0;
      this.emit('connected', { launchId });
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message:', data);
        this.emit('update', data);
        
        // Emit specific event types
        if (data.type) {
          this.emit(data.type, data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.emit('disconnected', { launchId });
      
      // Attempt reconnect
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => {
          console.log(`Reconnecting attempt ${this.reconnectAttempts}...`);
          this.connect(launchId);
        }, 1000 * this.reconnectAttempts);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  off(event: string, callback: Function) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event)!;
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  private emit(event: string, data: any) {
    if (this.listeners.has(event)) {
      this.listeners.get(event)!.forEach(callback => callback(data));
    }
  }

  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  // Add more event handlers
  // Add more event handlers with proper types
  private setupEventHandlers() {
    // Connection events
    this.on('connected', (data: WebSocketEventData) => {
      console.log('Connected to launch:', data.launchId);
    });

    this.on('disconnected', (data: WebSocketEventData) => {
      console.log('Disconnected from launch:', data.launchId);
    });

    // Token creation events
    this.on('token_created', (data: WebSocketEventData) => {
      console.log('Token created event:', data);
    });

    this.on('launch_started', (data: WebSocketEventData) => {
      console.log('Launch started:', data);
    });

    this.on('payload_sent', (data: WebSocketEventData) => {
      console.log('Payload sent:', data);
    });

    // Status events
    this.on('status_update', (data: WebSocketEventData) => {
      console.log('Status update:', data);
    });

    // Bot events
    this.on('bot_funding_start', (data: WebSocketEventData) => {
      console.log('Bot funding started:', data);
    });

    this.on('bot_funded', (data: WebSocketEventData) => {
      console.log('Bot funded:', data);
    });

    this.on('bot_buy_start', (data: WebSocketEventData) => {
      console.log('Bot buy started:', data);
    });

    this.on('bot_buy_complete', (data: WebSocketEventData) => {
      console.log('Bot buy complete:', data);
    });

    this.on('bot_activity', (data: WebSocketEventData) => {
      console.log('Bot activity:', data);
    });

    // Sell events
    this.on('sell_start', (data: WebSocketEventData) => {
      console.log('Sell started:', data);
    });

    this.on('sell_complete', (data: WebSocketEventData) => {
      console.log('Sell complete:', data);
    });

    this.on('sell_progress', (data: WebSocketEventData) => {
      console.log('Sell progress:', data);
    });

    // Launch completion events
    this.on('launch_completed', (data: WebSocketEventData) => {
      console.log('Launch completed:', data);
    });

    this.on('launch_failed', (data: WebSocketEventData) => {
      console.log('Launch failed:', data);
    });

    this.on('launch_error', (data: WebSocketEventData) => {
      console.log('Launch error:', data);
    });

    // Atomic launch specific events
    this.on('atomic_launch_start', (data: WebSocketEventData) => {
      console.log('Atomic launch start:', data);
    });

    this.on('atomic_create_and_buy', (data: WebSocketEventData) => {
      console.log('Atomic create and buy:', data);
    });

    // Pre-funding events
    this.on('prefund_start', (data: WebSocketEventData) => {
      console.log('Pre-fund start:', data);
    });

    this.on('prefund_progress', (data: WebSocketEventData) => {
      console.log('Pre-fund progress:', data);
    });

    this.on('prefund_complete', (data: WebSocketEventData) => {
      console.log('Pre-fund complete:', data);
    });

    // Transaction events
    this.on('transaction', (data: WebSocketEventData) => {
      console.log('Transaction:', data);
    });

    // Phase updates
    this.on('phase_update', (data: WebSocketEventData) => {
      console.log('Phase update:', data);
    });

    // Error events - this one is special since it might not be WebSocketEventData
    this.on('error', (error: any) => {
      console.error('WebSocket error:', error);
    });
  }

}

export const launchWebSocket = new LaunchWebSocket();


