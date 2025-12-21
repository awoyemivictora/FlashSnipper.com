// on-chain/performance-monitor.ts
export class PerformanceMonitor {
    private metrics = {
        snipeTimes: [] as number[],
        userFetchTimes: [] as number[],
        decryptionTimes: [] as number[],
        quoteTimes: [] as number[],
        transactionTimes: [] as number[]
    };
    
    private alerts: string[] = [];
    
    startTimer(): () => number {
        const start = performance.now();
        return () => performance.now() - start;
    }
    
    recordMetric(metric: keyof typeof this.metrics, value: number): void {
        this.metrics[metric].push(value);
        
        // Keep only last 100 measurements
        if (this.metrics[metric].length > 100) {
            this.metrics[metric].shift();
        }
        
        // Check for performance issues
        this.checkPerformance(metric, value);
    }
    
    private checkPerformance(metric: keyof typeof this.metrics, value: number): void {
        const thresholds = {
            snipeTimes: 5000, // 5 seconds max
            userFetchTimes: 3000, // 3 seconds
            decryptionTimes: 1000, // 1 second
            quoteTimes: 2000, // 2 seconds
            transactionTimes: 3000 // 3 seconds
        };
        
        if (value > thresholds[metric]) {
            const alert = `Performance alert: ${metric} took ${value.toFixed(0)}ms`;
            this.alerts.push(alert);
            console.warn(alert);
        }
    }
    
    getAverage(metric: keyof typeof this.metrics): number {
        const values = this.metrics[metric];
        if (values.length === 0) return 0;
        
        const sum = values.reduce((a, b) => a + b, 0);
        return sum / values.length;
    }
    
    getPerformanceReport(): any {
        return {
            averages: {
                snipeTime: this.getAverage('snipeTimes'),
                userFetchTime: this.getAverage('userFetchTimes'),
                decryptionTime: this.getAverage('decryptionTimes'),
                quoteTime: this.getAverage('quoteTimes'),
                transactionTime: this.getAverage('transactionTimes')
            },
            recentAlerts: this.alerts.slice(-10),
            timestamp: Date.now()
        };
    }
    
    clearAlerts(): void {
        this.alerts = [];
    }
}

