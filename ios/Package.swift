// swift-tools-version: 5.9
import PackageDescription
let package = Package(name:"RadarCore",platforms:[.macOS(.v13)],products:[.library(name:"RadarCore",targets:["RadarCore"])],targets:[.target(name:"RadarCore",path:"ResearchRadar/Sources",exclude:["RadarStore.swift","ResearchRadarApp.swift","ReadingViews.swift","WorkspaceViews.swift","SettingsViews.swift","DiscoveryViews.swift","DeepReadingView.swift","TechnologyViews.swift","FrontierViews.swift","ReadingQueueView.swift"],sources:["Models.swift"]),.testTarget(name:"RadarCoreTests",dependencies:["RadarCore"],path:"CoreTests")])
