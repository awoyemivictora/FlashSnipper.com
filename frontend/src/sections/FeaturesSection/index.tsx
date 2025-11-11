import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "react-router-dom";

export const FeaturesSection = (): JSX.Element => {
  const features = [
    {
      icon: "https://c.animaapp.com/mcs1777vCoVcpz/img/group.png",
      iconAlt: "Group",
      title: "Instant Sniping",
      description:
        "Quickly seize newly launched tokens to maximize your profit opportunities.",
      gradient: "from-blue-400 to-cyan-500",
    },
    {
      icon: "https://c.animaapp.com/mcs1777vCoVcpz/img/safety-tube-1.svg",
      iconAlt: "Safety tube",
      title: "Safety Filters and Controls",
      description:
        "Steer clear of scams and rug pulls with sophisticated token filters and security measures.",
      gradient: "from-green-400 to-emerald-500",
    },
    {
      icon: "https://c.animaapp.com/mcs1777vCoVcpz/img/data-visualization-1.svg",
      iconAlt: "Data visualization",
      title: "Intuitive User Dashboard",
      description:
        "Control settings, oversee trades, and monitor performance all in one user-friendly interface.",
      gradient: "from-purple-400 to-violet-500",
    },
    {
      icon: "https://c.animaapp.com/mcs1777vCoVcpz/img/schedule-1.svg",
      iconAlt: "Schedule",
      title: "Personalized RPC Integration",
      description:
        "Enhance speed and reliability by utilizing your favorite custom RPC endpoints.",
      gradient: "from-orange-400 to-red-500",
    },
    {
      icon: "https://c.animaapp.com/mcs1777vCoVcpz/img/earnings-1.svg",
      iconAlt: "Earnings",
      title: "Earnings Monitoring",
      description:
        "Keep track of your earnings with comprehensive trade history analysis.",
      gradient: "from-yellow-400 to-amber-500",
    },
    {
      icon: null,
      iconAlt: "Wallet",
      title: "Secure Funding Wallet",
      description:
        "Protect your assets with a uniquely generated, standalone funding wallet.",
      walletIcon: true,
      gradient: "from-indigo-400 to-purple-500",
    },
  ];

  return (
    <section className="relative w-full min-h-screen py-20 overflow-hidden bg-gradient-to-b from-[#021C14] via-[#021C14] to-emerald-900/20">

      {/* Icosahedron decorative element */}
      <div className="absolute top-1/2 -right-20 w-64 h-64 opacity-20 blur-lg rotate-45 hidden lg:block">
        <div className="relative w-full h-full">
          <img
            className="w-full h-full object-contain"
            alt="Icosahedron"
            src="https://c.animaapp.com/mcs1777vCoVcpz/img/icosahedron-1-1.png"
          />
        </div>
      </div>

      <div className="relative container mx-auto px-4 sm:px-6 lg:px-8 max-w-7xl">
        {/* Section Header */}
        <div className="text-center mb-16 lg:mb-20">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black bg-gradient-to-b from-white to-emerald-400 bg-clip-text text-transparent mb-6">
            Trade Smarter, Not Harder
          </h2>
          <p className="text-lg sm:text-xl text-white/80 max-w-4xl mx-auto leading-relaxed">
            Run your strategy on autopilot with powerful, round-the-clock
            automation. Just set your rules our bot handles the execution with
            speed, precision, and constant market awareness.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {features.map((feature, index) => (
            <Card
              key={index}
              className="group relative bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 hover:border-emerald-400/30 transition-all duration-300 hover:transform hover:-translate-y-2 hover:shadow-2xl hover:shadow-emerald-500/10"
            >
              <CardContent className="p-6 lg:p-8 h-full flex flex-col">
                {/* Icon Container */}
                <div className="mb-6">
                  {feature.walletIcon ? (
                    <div className="relative w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                      <div className="relative w-8 h-8">
                        <img
                          className="absolute w-5 h-7 top-0.5 left-1.5"
                          alt="Vector"
                          src="https://c.animaapp.com/mcs1777vCoVcpz/img/vector-1.svg"
                        />
                        <img
                          className="absolute w-3.5 h-7 top-0.5 left-2"
                          alt="Vector"
                          src="https://c.animaapp.com/mcs1777vCoVcpz/img/vector-3.svg"
                        />
                        <img
                          className="absolute w-2.5 h-1.5 top-1.5 left-3"
                          alt="Vector"
                          src="https://c.animaapp.com/mcs1777vCoVcpz/img/vector-4.svg"
                        />
                        <img
                          className="absolute w-1 h-1.5 top-1.5 left-4.5"
                          alt="Vector"
                          src="https://c.animaapp.com/mcs1777vCoVcpz/img/vector-2.svg"
                        />
                        <img
                          className="absolute w-8 h-3 top-5 left-0"
                          alt="Group"
                          src="https://c.animaapp.com/mcs1777vCoVcpz/img/group-1.png"
                        />
                      </div>
                    </div>
                  ) : feature.icon === "https://c.animaapp.com/mcs1777vCoVcpz/img/group.png" ? (
                    <div className="relative w-14 h-14 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                      <img
                        className="w-8 h-8"
                        alt={feature.iconAlt}
                        src={feature.icon}
                      />
                    </div>
                  ) : (
                    <div className={`w-14 h-14 bg-gradient-to-br ${feature.gradient} rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
                      <img
                        className="w-7 h-7"
                        alt={feature.iconAlt}
                        src={feature.icon ?? undefined}
                      />
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 flex flex-col">
                  <h3 className="text-xl font-bold text-white mb-3 group-hover:text-emerald-400 transition-colors duration-300">
                    {feature.title}
                  </h3>
                  <p className="text-white/70 leading-relaxed flex-1">
                    {feature.description}
                  </p>
                </div>

                {/* Hover effect line */}
                <div className="absolute bottom-0 left-0 w-0 h-0.5 bg-gradient-to-r from-emerald-400 to-cyan-400 group-hover:w-full transition-all duration-500"></div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* CTA Section */}
        <div className="text-center mt-16 lg:mt-20">
          <div className="inline-flex flex-col sm:flex-row gap-4 items-center bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-6 lg:p-8">
            <div className="text-left">
              <h3 className="text-2xl font-bold text-white mb-2">
                Ready to Start Sniping?
              </h3>
              <p className="text-white/70">
                Join thousands of traders using FlashSnipper to maximize their profits.
              </p>
            </div>

            <Link to="/trading-interface">
              <button className="px-8 py-3 bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-600 hover:to-cyan-700 rounded-full text-white font-semibold transition-all duration-300 hover:shadow-lg hover:shadow-emerald-500/25 whitespace-nowrap">
                Launch Sniper Now
              </button>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
};