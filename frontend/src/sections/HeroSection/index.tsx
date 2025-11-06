import React from "react";
import { Button } from "@/components/ui/Button";
import { Link } from "react-router-dom";

export const HeroSection = (): JSX.Element => {
  // Floating coin data
  const floatingCoins = [
    { name: "BONK", price: "0.0234", change: "+12.5%", color: "orange", position: "top-10 left-10" },
    { name: "WIF", price: "2.45", change: "+8.3%", color: "yellow", position: "top-20 right-16" },
    { name: "POPCAT", price: "0.567", change: "+45.2%", color: "blue", position: "bottom-32 left-20" },
    { name: "MYRO", price: "0.234", change: "+15.7%", color: "purple", position: "bottom-20 right-24" },
    { name: "JUP", price: "1.23", change: "+5.8%", color: "green", position: "top-1/3 left-1/4" },
    { name: "JTO", price: "3.45", change: "+9.1%", color: "red", position: "bottom-40 right-12" },
  ];

  const features = [
    { icon: "⚡", text: "Sub-Second Execution" },
    { icon: "🤖", text: "AI-Powered Analysis" },
    { icon: "🛡️", text: "Rug Pull Detection" },
    { icon: "📊", text: "Real-time Analytics" },
  ];

  return (
    <section className="relative w-full min-h-screen overflow-hidden bg-[#021C14]">
      {/* Animated Background Grid */}
      <div className="absolute inset-0 bg-[url('/images/img_grid_layers_v2.png')] bg-cover bg-center opacity-30 animate-pulse" />
      
      {/* Animated Gradient Orbs */}
      <div className="absolute top-1/4 -left-20 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl animate-float" />
      <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-float delay-2000" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-purple-500/5 rounded-full blur-3xl animate-float delay-1000" />

      {/* Main Content Container */}
      <div className="relative w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-32 pb-20 lg:pt-40 lg:pb-32">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          
          {/* Text Content */}
          <div className="flex flex-col items-start gap-8 z-10">
            {/* Badge */}
            <div className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 rounded-full border border-emerald-500/30 backdrop-blur-sm">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-emerald-400 text-sm font-semibold">LIVE TRADING ACTIVE</span>
            </div>

            {/* Main Heading */}
            <h1 className="font-black text-white text-4xl sm:text-5xl lg:text-6xl xl:text-7xl leading-tight sm:leading-tight lg:leading-tight tracking-tight">
              <span className="block bg-gradient-to-r from-white to-emerald-200 bg-clip-text text-transparent">
                Flash AI
              </span>
              <span className="block mt-2">
                <span className="text-transparent bg-gradient-to-r from-emerald-400 to-green-300 bg-clip-text">
                  Memecoin Hunter
                </span> 🚀
              </span>
            </h1>

            {/* Description */}
            <p className="text-xl sm:text-2xl lg:text-3xl text-white/80 leading-relaxed max-w-2xl font-semibold">
              Our AI scans, predicts, and snipes trending memecoins{" "}
              <span className="text-emerald-400 font-bold">before the crowd</span>.
            </p>

            {/* Feature Pills */}
            <div className="flex flex-wrap gap-3 mt-4">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 px-4 py-3 bg-white/5 rounded-2xl border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-all duration-300 cursor-pointer group"
                >
                  <span className="text-lg">{feature.icon}</span>
                  <span className="text-white text-sm font-medium group-hover:text-emerald-400 transition-colors">
                    {feature.text}
                  </span>
                </div>
              ))}
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 sm:gap-6 mt-6">
              <Link to="/trading-interface">
                <Button className="group flex items-center justify-center gap-3 px-10 sm:px-12 py-6 bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-600 hover:to-green-700 rounded-2xl border-0 shadow-2xl transition-all duration-300 hover:scale-105 hover:shadow-2xl min-w-[220px] relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                  <span className="text-white text-lg font-bold whitespace-nowrap relative z-10">
                    🚀 Launch Sniper
                  </span>
                </Button>
              </Link>
              
              <Button 
                variant="outline"
                className="group flex items-center justify-center gap-3 px-10 sm:px-12 py-6 bg-transparent hover:bg-white/10 rounded-2xl border-2 border-emerald-500/50 text-white transition-all duration-300 hover:scale-105 hover:border-emerald-400 min-w-[220px]"
              >
                <span className="text-lg font-semibold whitespace-nowrap group-hover:text-emerald-400">
                  📚 Learn More
                </span>
              </Button>
            </div>

            {/* Stats */}
            <div className="flex flex-wrap gap-8 sm:gap-12 mt-8 p-6 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-sm">
              <div className="text-center">
                <div className="text-2xl sm:text-3xl font-bold text-emerald-400">1.2K+</div>
                <div className="text-white/60 text-sm font-medium">Active Traders</div>
              </div>
              <div className="text-center">
                <div className="text-2xl sm:text-3xl font-bold text-emerald-400">$86M+</div>
                <div className="text-white/60 text-sm font-medium">Volume Traded</div>
              </div>
              <div className="text-center">
                <div className="text-2xl sm:text-3xl font-bold text-emerald-400">94.7%</div>
                <div className="text-white/60 text-sm font-medium">Success Rate</div>
              </div>
              <div className="text-center">
                <div className="text-2xl sm:text-3xl font-bold text-emerald-400">0.3s</div>
                <div className="text-white/60 text-sm font-medium">Avg. Speed</div>
              </div>
            </div>
          </div>

          {/* Image Container with Enhanced Floating Elements */}
          <div className="relative order-first lg:order-last">
            <div className="relative w-full max-w-lg lg:max-w-xl xl:max-w-2xl mx-auto">
              
              {/* Main Laptop Image */}
              <div className="relative z-20">
                <img
                  src="/images/side-view-male-hacker-with-gloves-laptop 1.png"
                  alt="AI Memecoin Hunter Interface"
                  className="w-full h-auto object-contain transform scale-110 lg:scale-125 drop-shadow-2xl"
                />
              </div>

              {/* Floating Coin Elements */}
              {floatingCoins.map((coin, index) => (
                <div
                  key={coin.name}
                  className={`absolute ${coin.position} z-30 animate-float-slow delay-${index * 300}`}
                >
                  <div className="relative group">
                    <div className="flex items-center gap-2 px-4 py-3 bg-black/90 backdrop-blur-md rounded-2xl border border-white/20 shadow-2xl transform transition-all duration-300 group-hover:scale-110 group-hover:border-emerald-400/50">
                      <div className={`w-3 h-3 bg-${coin.color}-400 rounded-full`} />
                      <div className="text-center">
                        <div className="text-white font-bold text-sm">{coin.name}</div>
                        <div className="text-emerald-400 font-semibold text-xs">{coin.price}</div>
                        <div className="text-green-400 text-xs font-bold">{coin.change}</div>
                      </div>
                    </div>
                    {/* Connection line to laptop */}
                    <div className="absolute w-20 h-px bg-gradient-to-r from-emerald-400/50 to-transparent top-1/2 -left-20 transform -rotate-45 opacity-60 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              ))}

              {/* Enhanced Code Window */}
              <div className="absolute top-1/4 -left-4 lg:-left-8 w-56 lg:w-72 bg-gradient-to-br from-black/95 to-gray-900/95 backdrop-blur-lg rounded-3xl border border-emerald-500/40 p-5 shadow-2xl transform -rotate-3 animate-float">
                <div className="flex gap-2 mb-4">
                  <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                </div>
                <div className="text-xs lg:text-sm font-mono space-y-1">
                  <div className="text-emerald-400">$ flashai --snipe</div>
                  <div className="text-white/60">Scanning new pools...</div>
                  <div className="text-green-400">✓ Found 12 opportunities</div>
                  <div className="text-blue-400">→ Executing trades...</div>
                  <div className="text-emerald-300 font-bold">💰 Profit: +2.4 SOL</div>
                </div>
              </div>

              {/* Enhanced Price Alert */}
              <div className="absolute bottom-1/4 -right-4 lg:-right-8 w-48 lg:w-60 bg-gradient-to-br from-black/95 to-blue-900/95 backdrop-blur-lg rounded-3xl border border-blue-500/40 p-5 shadow-2xl transform rotate-3 animate-float delay-1000">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                  <div className="text-blue-400 font-bold text-sm">LIVE ALERT</div>
                </div>
                <div className="text-sm">
                  <div className="text-white font-bold text-lg">SOL $146.89</div>
                  <div className="text-green-400 font-semibold">+3.2% 📈</div>
                  <div className="text-white/60 text-xs mt-2">New meme coin detected</div>
                </div>
              </div>

              {/* AI Analysis Panel */}
              <div className="absolute top-10 right-10 w-44 lg:w-52 bg-gradient-to-br from-purple-900/90 to-pink-900/90 backdrop-blur-lg rounded-3xl border border-purple-500/40 p-4 shadow-2xl transform rotate-6 animate-float delay-500">
                <div className="flex items-center gap-2 mb-2">
                  <div className="text-purple-400 text-lg">🧠</div>
                  <div className="text-white font-bold text-sm">AI ANALYSIS</div>
                </div>
                <div className="space-y-1 text-xs">
                  <div className="text-green-400">High Potential: 87%</div>
                  <div className="text-yellow-400">Risk Level: Low</div>
                  <div className="text-white/60">Trending: #memecoins</div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>

      {/* Bottom Gradient */}
      <div className="absolute bottom-0 left-0 w-full h-48 bg-gradient-to-t from-[#021C14] to-transparent pointer-events-none" />

      {/* Floating Particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-emerald-400/30 rounded-full animate-float"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${3 + Math.random() * 4}s`
            }}
          />
        ))}
      </div>
    </section>
  );
};