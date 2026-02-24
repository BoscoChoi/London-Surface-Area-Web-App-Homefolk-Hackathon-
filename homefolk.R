## homefolk Sustainable Housing Hackathon

getwd()
# load the full ONS Postcode Directory (2025) dataset
ONS2025_UK <- read.csv("Documents/homefolk Hackathon/ONSPD_MAY_2025/Data/ONSPD_MAY_2025_UK.csv")
# preview the first few rows to inspect structure
head(ONS2025_UK)
# keep only the postcode, output areas (from 2021 census data) and region code columns 
keep <- ONS2025_UK[, c("pcds", "oa21", "rgn")]
# filter dataset to London postcodes with valid OA codes
London_2025 <- keep[keep$rgn == "E12000007" & keep$oa21 != "", ]
# remove possible duplicates of postcode-OA pairs
London_2025 <- unique(London_2025)
# preview the first few rows of the London-only data frame
head(London_2025)
# save data frame as a CSV file for use in Python
write.csv(London_2025,
          "Documents/homefolk Hackathon/ONSPD_MAY_2025/Data/london_postcode_to_oa21_2025.csv",
          row.names = FALSE)




