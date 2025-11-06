import { useEffect, useRef, useState, useCallback } from "react";
import { executeTrade } from "../services/trade";
import { getTokenPrice } from "../services/trade";

// Configuration
const MONITOR_INTERVAL_MS = 60000;  // Check every 60 seconds
const BACKEND_API_URL = 'https://localhost:8000';


export const useTradeMonitor = (walletKeypair, walletAddress, authToken, logToUI) => {
    const [activePositions, setActivePositions] = useState([]);
    const intervalRef = useRef(null);

    const fetchActivePositions = useCallback(async () => {
        if (!authToken || !walletAddress) return;
        try {
            const response = await fetch(`${BACKEND_API_URL}/user/active-trades?wallet_address=${walletAddress}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            if (!response.ok) {
                throw new Error(`Failed to fetch active trades: ${response.statusText}`);
            }
            const data = await response.json();
            setActivePositions(data);   // Assuming backend returns a list of active trades
            logToUI(`Fetched ${data.length} active positions to monitor.`);
        } catch (error) {
            logToUI(`Error fetching active positions: ${error.message}`);
            console.error("Error fetching active positions:", error);
        }
    }, [authToken, walletAddress, logToUI]);

    

    const monitorAndExecuteSell = useCallback(async (position) => {
        // This is a simplified version of your monitor.js logic
        const { mint_address, entry_price, stop_loss, take_profit, token_amounts_purchased, token_name, token_decimals } = position;

        try {
            // Get current price of the token 
            const currentTokenPricePerUnit = await getTokenPrice(mint_address);
            if (!currentTokenPricePerUnit) {
                logToUI(`Could not get current price for ${token_name}. Skipping monitor.`);
                return;
            }

            const currentTotalHoldingValue = currentTokenPricePerUnit * token_amounts_purchased;

            logToUI(`Monitoring ${token_name} (${mint_address}): Current Total Value: $${currentTotalHoldingValue.toFixed(6)}`);

            let sellReason = null;
            if (currentTotalHoldingValue >= take_profit) {
                logToUI(`TAKE PROFIT for ${token_name}! Current value: $${currentTotalHoldingValue.toFixed(6)}`);
                sellReason = "Take Profit";
            } else if (currentTotalHoldingValue <= stop_loss) {
                logToUI(`STOP LOSS for ${token_name}! Current value: $${currentTotalHoldingValue.toFixed(6)}`);
                sellReason = "Stop Loss";
            }

            if (sellReason) {
                logToUI(`Initiating SELL for ${token_name} due to ${sellReason}.`);
                const result = await executeTrade(walletKeypair, walletAddress, authToken, {
                    mint_address: mint_address,
                    amount_sol: token_amounts_purchased,    // Amount of tokens to sell
                    trade_type: "sell",
                    token_symbol: token_name,
                    previousBuyPrice: entry_price,  // Pass original buy price for profit calc
                    reason: sellReason
                });

                if (result.success) {
                    logToUI(`Successfully sold ${token_name} (${sellReason}).`);
                    // After successful sell, re-fetch active positions to update UI
                    await fetchActivePositions;
                } else {
                    logToUI(`Failed to sell ${token_name}: ${result.error}`);
                }
            } else {
                logToUI(`${token_name}: Not yet at SL/TP.`);
            }
            
        } catch (error) {
            logToUI(`Error monitoring/selling ${token_name}: ${error.message}`);
            console.error(`Error monitoring/selling ${token_name}:`, error);
        }
    } , [walletKeypair, walletAddress, authToken, logToUI, fetchActivePositions]);



    // Main monitoring loop
    useEffect(() => {
        // Clear any existing interval first
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }

        if (authToken && walletAddress && activePositions.length > 0) {
            // Run immediately on first load, then every interval
            const runMoonitorCycle = async () => {
                logToUI("Starting monitoring cycle...");
                for (const position of activePositions) {
                    await monitorAndExecuteSell(position);
                }
                logToUI("Monitoring cycle complete.");
            };
            runMoonitorCycle(); // Run once immediately

            intervalRef.current = setInterval(runMoonitorCycle, MONITOR_INTERVAL_MS);
        }

        
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [authToken, walletAddress, activePositions, logToUI, monitorAndExecuteSell]);

    
    // Fetch initial positions when component mounts or auth changes
    useEffect(() => {
        fetchActivePositions();
    }, [fetchActivePositions]);


    return null;    // This hook doesn't render anything directly
};










