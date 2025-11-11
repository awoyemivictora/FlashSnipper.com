import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export const FAQSection = (): JSX.Element => {
  const faqItems = [
    {
      question: "What is FlashSnipper, and how can it improve my trading experience?",
      answer: "FlashSnipper is the quickest automated sniper bot for Solana, designed to execute trades on newly launched tokens instantly. By utilizing real-time monitoring of liquidity pools and integrating smoothly with your Solana wallet, it enhances the buying and selling experience—allowing you to seize optimal entry points and maximize your profit potential.",
      icon: "🚀"
    },
    {
      question: "How does FlashSnipper work?",
      answer: "The tool constantly scans the Solana blockchain, keeping an eye on liquidity pools for new token listings. Once a token that meets your criteria is found, FlashSnipper promptly activates orders to purchase tokens and carry out selling orders via your connected Solana wallet, ensuring you never overlook a lucrative opportunity.",
      icon: "⚡"
    },
    {
      question: "What are the fees for using FlashSnipper?",
      answer: "Using FlashSnipper is free—only a 1% fee applies to each successful trade as a post-trade charge, meaning you only pay when you profit. This clear fee structure keeps transaction costs low and predictable.",
      icon: "💎"
    },
    {
      question: "Is FlashSnipper safe to use?",
      answer: "Yes! FlashSnipper includes advanced safety filters, rug pull detection, and works with your existing Solana wallet. We never have access to your private keys, and all transactions require your approval.",
      icon: "🛡️"
    },
    {
      question: "What makes FlashSnipper different from other sniper bots?",
      answer: "FlashSnipper offers instant execution, advanced safety features, customizable RPC endpoints, and an intuitive dashboard. Our premium filters help you avoid scams while our speed ensures you get in early on legitimate projects.",
      icon: "🎯"
    },
    {
      question: "Do I need technical knowledge to use FlashSnipper?",
      answer: "Not at all! FlashSnipper is designed with both beginners and advanced traders in mind. The intuitive interface guides you through setup, and our documentation helps you get started quickly.",
      icon: "👨‍💻"
    }
  ];

  return (
    <section className="relative w-full min-h-screen py-12 sm:py-16 lg:py-20 overflow-hidden bg-gradient-to-b from-[#021C14] via-[#021C14] to-emerald-900/20">
      {/* Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-20 -right-20 w-60 h-60 bg-emerald-500/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute -bottom-20 -left-20 w-60 h-60 bg-cyan-500/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
        
      </div>

      <div className="relative container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
        {/* Section Header */}
        <div className="text-center mb-12 sm:mb-16 lg:mb-20">
          <div className="inline-flex items-center gap-2 sm:gap-3 bg-emerald-500/10 border border-emerald-400/30 rounded-full px-3 sm:px-4 py-1.5 sm:py-2 mb-4 sm:mb-6">
            <span className="text-emerald-400 text-xs sm:text-sm font-semibold">FAQ</span>
          </div>
          <h2 className="text-2xl sm:text-3xl lg:text-4xl xl:text-5xl font-black bg-gradient-to-b from-white to-emerald-400 bg-clip-text text-transparent mb-4 sm:mb-6">
            Frequently Asked Questions
          </h2>
          <p className="text-base sm:text-lg lg:text-xl text-white/80 max-w-2xl mx-auto leading-relaxed px-4">
            Get all the answers to the most common questions about FlashSnipper and start trading smarter today.
          </p>
        </div>

        {/* FAQ Accordion */}
        <div className="bg-white/5 backdrop-blur-sm rounded-2xl sm:rounded-3xl border border-white/10 p-4 sm:p-6 lg:p-8">
          <Accordion type="single" collapsible className="w-full space-y-3 sm:space-y-4">
            {faqItems.map((item, index) => (
              <AccordionItem
                key={`faq-${index}`}
                value={`item-${index}`}
                className="bg-white/5 rounded-xl sm:rounded-2xl border border-white/10 overflow-hidden hover:border-emerald-400/20 transition-all duration-300"
              >
                <AccordionTrigger className="flex items-start gap-3 sm:gap-4 text-left w-full px-4 sm:px-6 py-4 sm:py-5 hover:no-underline hover:bg-white/5 transition-all duration-200 group [&[data-state=open]>div>div>svg]:text-emerald-400">
                  <div className="flex items-start gap-3 sm:gap-4 w-full">
                    <div className="flex-shrink-0 w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-br from-emerald-500 to-cyan-600 rounded-lg sm:rounded-xl flex items-center justify-center text-base sm:text-lg group-hover:scale-110 transition-transform duration-300 mt-0.5">
                      {item.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base sm:text-lg font-bold text-white text-left group-hover:text-emerald-400 transition-colors duration-300 pr-8 sm:pr-12 leading-relaxed">
                        {item.question}
                      </h3>
                    </div>
                    <div className="flex-shrink-0 transition-transform duration-300 group-data-[state=open]:rotate-180 mt-1">
                      <svg 
                        className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path 
                          strokeLinecap="round" 
                          strokeLinejoin="round" 
                          strokeWidth={2} 
                          d="M19 9l-7 7-7-7" 
                        />
                      </svg>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-4 sm:px-6 pb-4 sm:pb-5 pt-1 sm:pt-2 text-emerald-400 [&>div>p]:text-white/70">
                  <div className="pl-0 sm:pl-14">
                    <p className="text-white/70 leading-relaxed text-sm sm:text-base lg:text-lg">
                      {item.answer}
                    </p>
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>

        {/* CTA Section */}
        <div className="text-center mt-12 sm:mt-16">
          <div className="bg-gradient-to-r from-emerald-500/10 to-cyan-600/10 backdrop-blur-sm rounded-2xl sm:rounded-3xl border border-emerald-400/30 p-6 sm:p-8 lg:p-12">
            <h3 className="text-xl sm:text-2xl lg:text-3xl font-bold text-white mb-3 sm:mb-4">
              Still have questions?
            </h3>
            <p className="text-white/70 text-base sm:text-lg mb-6 sm:mb-8 max-w-2xl mx-auto px-4">
              Our support team is here to help you get the most out of FlashSnipper.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
              <button className="px-6 sm:px-8 py-2.5 sm:py-3 bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-600 hover:to-cyan-700 rounded-full text-white font-semibold transition-all duration-300 hover:shadow-lg hover:shadow-emerald-500/25 text-sm sm:text-base">
                Contact Support
              </button>
              <button className="px-6 sm:px-8 py-2.5 sm:py-3 bg-white/10 hover:bg-white/20 border border-white/20 rounded-full text-white font-semibold transition-all duration-300 backdrop-blur-sm text-sm sm:text-base">
                Join Community
              </button>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6 mt-12 sm:mt-16">
          <div className="text-center p-3 sm:p-4 bg-white/5 rounded-xl sm:rounded-2xl border border-white/10">
            <div className="text-xl sm:text-2xl lg:text-3xl font-bold text-emerald-400 mb-1 sm:mb-2">24/7</div>
            <div className="text-white/60 text-xs sm:text-sm">Active Monitoring</div>
          </div>
          <div className="text-center p-3 sm:p-4 bg-white/5 rounded-xl sm:rounded-2xl border border-white/10">
            <div className="text-xl sm:text-2xl lg:text-3xl font-bold text-emerald-400 mb-1 sm:mb-2">1%</div>
            <div className="text-white/60 text-xs sm:text-sm">Success Fee Only</div>
          </div>
          <div className="text-center p-3 sm:p-4 bg-white/5 rounded-xl sm:rounded-2xl border border-white/10">
            <div className="text-xl sm:text-2xl lg:text-3xl font-bold text-emerald-400 mb-1 sm:mb-2">Instant</div>
            <div className="text-white/60 text-xs sm:text-sm">Trade Execution</div>
          </div>
          <div className="text-center p-3 sm:p-4 bg-white/5 rounded-xl sm:rounded-2xl border border-white/10">
            <div className="text-xl sm:text-2xl lg:text-3xl font-bold text-emerald-400 mb-1 sm:mb-2">Secure</div>
            <div className="text-white/60 text-xs sm:text-sm">Wallet Integration</div>
          </div>
        </div>
      </div>
    </section>
  );
};