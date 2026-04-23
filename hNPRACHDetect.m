function [indout,offset,detinfo] = hNPRACHDetect(ue,chs,waveform,varargin)
%hNPRACHDetect Detect NB-IoT physical random access channel
%   [INDOUT,OFFSET,DETINFO] = hNPRACHDetect(UE,CHS,WAVEFORM) detects a
%   narrowband physical random access channel (NPRACH) transmission in the
%   input WAVEFORM and returns the detected value of the initial subcarrier
%   for NPRACH, INDOUT, the timing offset, OFFSET, and the detection
%   information, DETINFO. The function implements the algorithm referred to
%   in [1] as "Differential Processing With Minimum Combinations". This
%   algorithm matches the received waveform with a reference frequency
%   hopping pattern. The function generates a reference pattern for all
%   values of the initial subcarrier, NInit, allowed for the current NPRACH
%   configuration. For each value of NInit, the function performs these
%   steps:
%   1. Generates a vector 'v' containing the magnitude of the frequency
%      hopping of the received waveform. The position of the received
%      frequency hopping in the vector 'v' depends on the reference
%      frequency hopping.
%   2. Generates the spectrum of 'v' and stores the value of its highest
%      peak.
%   The function returns the value of NInit corresponding to the highest
%   peak of the spectrum among all those that exceed a defined threshold.
%
%   UE is a structure including these fields:
%   NNCellID              - Narrowband cell identity (0...503)
%   NBULSubcarrierSpacing - NB-IoT uplink subcarrier spacing
%                           ('3.75kHz','15kHz')
%
%   CHS is a structure including these fields:
%   NPRACHFormat     - Preamble format ('0','1','2')
%   Periodicity      - NPRACH resource periodicity in ms
%                      (nprach-Periodicity)
%                      (40,80,160,320,640,1280,2560) for preamble format
%                      0/1, or (40,80,160,320,640,1280,2560,5120) for
%                      preamble format 2
%   SubcarrierOffset - Frequency location of the first subcarrier
%                      allocated to NPRACH (nprach-SubcarrierOffset)
%                      (0,2,12,18,24,34,36) for preamble format 0/1, or
%                      (0,6,12,18,24,36,42,48,54,60,72,78,84,90,102,108)
%                      for preamble format 2
%   NumSubcarriers   - Number of subcarriers allocated to NPRACH
%                      (nprach-NumSubcarriers)
%                      (12,24,36,48) for preamble format 0/1, or
%                      (36,72,108,144) for preamble format 2
%   NRep             - Number of NPRACH repetitions
%                      (numRepetitionsPerPreambleAttempt)
%                      (1,2,4,8,16,32,64,128)
%   StartTime        - Optional. NPRACH starting time in ms
%                      (nprach-StartTime)
%                      (8,16,32,64,128,256,512,1024) (default 8)
%
%   WAVEFORM is a time-domain waveform, specified as an N-by-P matrix. N is
%   the number of time-domain samples and P is the number of receive
%   antennas. If N is less than the minimum number of samples needed to
%   analyze this configuration, the function appends zeros at the end of
%   the waveform. If WAVEFORM contains multiple NPRACH instances, the
%   function returns the value of the initial subcarrier, INDOUT, and
%   timing offset, OFFSET, related to the NPRACH instance with the highest
%   peak of the spectrum.
%
%   INDOUT is the value of the initial subcarrier for NPRACH corresponding
%   to the highest peak across all valid values of NInit. If such a peak
%   does not exceed the defined detection threshold, INDOUT is empty.
%
%   OFFSET is the timing offset of the NPRACH waveform from the origin of
%   the input WAVEFORM, returned in samples at the sampling rate of the
%   given NPRACH and UE configurations. When INDOUT is empty, OFFSET is
%   empty.
%
%   DETINFO is a structure containing these fields:
%
%   DetectionPeaks     - Highest peaks of the spectrum used for the
%                        detection, where each value corresponds to a value
%                        of the initial subcarrier for NPRACH, NInit.
%   DetectionThreshold - Threshold that the function uses for the preamble
%                        detection. Its value is either the user-defined
%                        value or the default value computed internally.
%
%   [INDOUT,OFFSET,DETINFO] = hNPRACHDetect(...,THRESHOLD) specifies the
%   detection threshold as a real number in the range 0 to 1. When this
%   input is not present or set to [], the function selects a default value
%   specific to the NPRACH format and number of repetitions, NRep.
%   
%   Example:
%   % Detect an NPRACH preamble which has been delayed by 7 samples.
%   ue.NNCellID = 0;
%   ue.NBULSubcarrierSpacing = '15kHz';
%   chs.NPRACHFormat = '0';
%   chs.Periodicity = 80;
%   chs.SubcarrierOffset = 0;
%   chs.NumSubcarriers = 12;
%   chs.NRep = 1;
%   chs.NInit = 2;
%   tx = lteNPRACH(ue,chs);
%   rx = [zeros(7,1); tx]; % delay NPRACH 
%   [index,offset] = hNPRACHDetect(ue,chs,rx)
%   
%   See also lteNPRACH, lteNPRACHInfo.

%   Copyright 2022 The MathWorks, Inc.

%   References:
%   [1] Chougrani et al., "Efficient Preamble Detection and Time-of-Arrival
%   Estimation for Single-Tone Frequency Hopping Random Access in NB-IoT",
%   IEEE Internet of Things Journal, Vol. 8, No. 9, 2021.

    narginchk(3,4);

    % Parse and validate inputs
    [chs,nprachInfo,threshold] = validateParameters(ue,chs,waveform,varargin{:});

    % Pre-configure empty outputs
    indout = [];
    offset = [];
    detinfo = struct('DetectionThreshold',threshold,'DetectionPeaks',zeros(0,1));

    % Compute useful parameters
    SR = nprachInfo.SamplingRate;
    NRxAnts = size(waveform,2); % Number of receive antennas
    params = nprachInfo.PreambleParameters;
    Ts2Samples = 1/30720*SR/1000; % Conversion from Ts to samples
    numSymbolGroups = chs.NRep*params.P; % Number of symbol groups (SGs)
    totalActiveSC = nprachInfo.K*nprachInfo.NULSC; % Total number of UL subcarriers reserved for NPRACH
    firstActiveSC = (nprachInfo.Nfft/2) - totalActiveSC/2 + chs.SubcarrierOffset; % First active subcarrier (0-based)
    nsymbols = params.N; % Number of symbols in a SG
    duration = (params.T_SEQ + params.T_CP)*Ts2Samples; % SG length in samples
    start = round(chs.StartTime*30720*Ts2Samples); % Starting symbol (0-based) in samples
    nFFT = 256; % FFT size to generate 'U' in Eq. (11)

    % Define the maximum length of the window for the search for the peak
    % as the length of the CP plus the maximum timing tolerance. This
    % search window is scaled considering the value of nFFT defined above.
    searchWindow = min(nFFT,(params.T_CP*Ts2Samples + ceil(3.646/1e6*SR))*(nFFT/nprachInfo.Nfft));

    % Define the maximum number of subcarriers for frequency hopping,
    % maxSCS, and the maximum number of contiguous preambles that exist
    % before a 40 ms gap is added to the NPRACH transmission.
    if chs.NPRACHFormat=="2"
        maxSCS = 18;
        maxContiguousPreambles = 16;
    else % Format 0 or 1
        maxSCS = 6;
        maxContiguousPreambles = 64;
    end
    maxContiguousSymbolGroups = maxContiguousPreambles*params.P;
    gapSamples = 40*SR/1000; % 40 ms gap in number of samples
    numGaps = fix((chs.NRep - 1)/maxContiguousPreambles);

    % Pad the input waveform with zeros, if it has less samples than the
    % minimum amount that the algorithm needs
    numSamplesNeeded = start + nsymbols*duration + numGaps*gapSamples;
    if size(waveform,1)<numSamplesNeeded
        waveform = [waveform; zeros(numSamplesNeeded - size(waveform,1),NRxAnts)];
    end

    % Perform half subcarrier frequency shift
    t = ((0:size(waveform,1) - 1)/SR).';
    waveform = waveform.*repmat(exp(-1i*pi*nprachInfo.SubcarrierSpacing*t),1,size(waveform,2));

    % Check each frequency hopping pattern
    X = cell(chs.NumSubcarriers,1);
    detMet = zeros(chs.NumSubcarriers,1);
    normY = nsymbols*nprachInfo.Nfft; % Expected value of each element of 'Y' for this NPRACH configuration
    for ninit = 0:(chs.NumSubcarriers-1)

        % Compute the frequency hopping pattern Delta for this value of NInit
        chs.NInit = ninit;
        nprachInfo = lteNPRACHInfo(ue,chs);
        Delta = diff(nprachInfo.FrequencyLocation);
        Delta = wrapToMaxSCS(Delta,maxSCS);

        % For each receive antenna
        maxU2 = 0;
        for p = 1:NRxAnts
            % For each SG m:
            % 1. Remove cyclic prefix (CP)
            % 2. Perform FFT for each symbol 'i'
            % 3. Combine all symbols in a SG to get 'Y'
            % 4. Compute 'Z'
            % 5. Create 'v' and populate it with 'Z'
            % 6. Perform nFFT-point FFT on 'v' to generate its spectrum 'U'
            Y = zeros(numSymbolGroups,1);
            v = zeros(2*maxSCS + 1,1);
            NGap = 0; % Number of 40 ms gaps to consider when extracting the current SG
            for m = 1:numSymbolGroups

                % Check whether a new 40 ms gap needs to be considered
                if m>maxContiguousSymbolGroups && mod(m,maxContiguousSymbolGroups)==1
                    NGap = NGap+1;
                end

                % Get the samples for this SG
                rxWave = waveform(start + NGap*gapSamples + ((m - 1)*duration) + (1:duration),p);

                % 1) Remove CP
                rxWaveNoCP = rxWave(params.T_CP*Ts2Samples + 1:end);

                % 2) Perform FFT for each symbol in a SG - Eqs. (3)-(4)-(5)
                % 3) Combine all symbols in a SG to get 'Y' - Eq. (6)
                symbol = reshape(rxWaveNoCP,[],nsymbols);
                symbol = symbol./(rms(symbol) + eps); % Normalize the received symbol against its RMS to take care of any channel gain
                symbolFFT = fftshift(fft(symbol),1);
                activeSCs = symbolFFT(firstActiveSC + (1:chs.NumSubcarriers),:);
                Y(m) = sum(activeSCs(nprachInfo.FrequencyLocation(m) + 1,:));
                Y(m) = Y(m)/normY; % Normalize 'Y' against the expected value

                if m > 1
                    % 4) Compute 'Z' - Eq. (7)
                    Z = Y(m - 1)*conj(Y(m));

                    % 5) Populate 'v' with 'Z', as shown in Fig. 3
                    v(maxSCS + 1 + Delta(m - 1)) = v(maxSCS + 1 + Delta(m - 1)) + Z;
                end
            end

            % 6) Perform nFFT-point FFT on 'v' to generate its spectrum 'U' - Eqs. (11)-(14)
            U = fft(v,nFFT);
            U2 = abs(U).^2;
            maxU2 = maxU2 + max(U2);

            % 7) Combine spectra from each receive antenna - Eq. (14)
            if (p==1)
                X{ninit + 1} = U2;
            else
                X{ninit + 1} = X{ninit + 1} + U2;
            end

        end

        % Generate the reference spectrum for this value of NInit
        vRef = histcounts(Delta,numel(v));
        U2Ref = abs(fft(vRef,nFFT)).^2;

        % Normalize the spectrum. Add eps to the normalization to avoid
        % dividing by 0.
        normE = sqrt(maxU2*max(U2Ref)*NRxAnts);
        X{ninit+1} = X{ninit + 1}/(normE + eps);

        % Store detection peak for this value of NInit
        detMet(ninit + 1) = sqrt(max(X{ninit + 1}(1:searchWindow)));
    end

    % 8) Detect frequency hopping pattern. The implementation detects a
    % single NInit value with the highest peak across all values, provided
    % a detection threshold is exceeded.
    [highPeak,idx] = max(detMet);

    % If the highest peak for this NInit value exceeds the detection
    % threshold, establish the detected NInit and timing offset
    if (highPeak>=threshold)
        [~,kMax] = max(X{idx}(1:searchWindow));
        indout = idx - 1;

        % Perform time of arrival estimation - Eq. (17)
        D1 = kMax - 1;
        if kMax==1 || kMax==nFFT
            epsilon = 0;
        else
            alpha = X{idx}(kMax - 1);
            beta = highPeak;
            gamma = X{idx}(kMax + 1);
            epsilon = 0.5*(gamma - alpha)/(2*beta - alpha - gamma);
        end
        offset = (D1 + epsilon)*(nprachInfo.Nfft/nFFT); % Time offset estimation in samples at the NPRACH sampling rate
    end
    % Populate the output detection information structure
    detinfo.DetectionPeaks = detMet;

end

% Parse and validate inputs
function [chs,nprachInfo,thres] = validateParameters(ue,chs,rxwave,varargin)

    % Assign default value to the optional CHS field StartTime
    chs = mwltelibrary('validateLTEParameters',chs,'StartTime');
    chs.StartTime = double(chs.StartTime);

    % Validate input UE and CHS parameters by calling lteNPRACHInfo
    nprachInfo = lteNPRACHInfo(ue,chs);

    % Validate waveform
    fcnName = 'hNPRACHDetect';
    validateattributes(rxwave,{'numeric'},{'2d','finite','nonnan'},fcnName,'Waveform');

    % Get the value of the detection threshold
    if nargin<4 || isempty(varargin{1})
        % The default value of the detection threshold has been empirically
        % determined based on the probability of false alarm and the
        % probability of detection for the conformance tests discussed in
        % Section 8.5.3 of TS 36.141.
        if chs.NPRACHFormat=="2"
            thres = 0.017 - 0.002*log2(chs.NRep);
        else % NPRACHFormat 0 or 1
            thres = 0.025 - 0.003*log2(chs.NRep);
        end
    else
        % User-defined value for the detection threshold
        t = varargin{1};
        validateattributes(t,{'numeric'},...
            {'scalar','real','>=',0,'<=',1},fcnName,'DetectionThreshold');
        thres = double(t); 
    end

end

function Delta = wrapToMaxSCS(Delta,maxSCS)
    % Wrap Delta according to the maximum subcarrier spacing between two
    % consecutive symbol groups, |maxSCS|. Positive multiples of
    % |maxSCS| map to |maxSCS| and negatve multiples of |maxSCS| map to
    % -|maxSCS|.
    Delta(abs(Delta)>maxSCS) = -sign(Delta(abs(Delta)>maxSCS)).*(2*maxSCS-abs(Delta(abs(Delta)>maxSCS)));
end
