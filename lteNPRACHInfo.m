%lteNPRACHInfo NPRACH resource information
%   INFO = lteNPRACHInfo(UE,CHS) returns a structure containing narrowband
%   physical random access channel (NPRACH) information given UE-specific
%   settings structure UE and channel transmission configuration structure
%   CHS.
%
%   UE must be a structure including these fields:
%   NNCellID              - Narrowband cell identity (0...503)
%   NBULSubcarrierSpacing - NB-IoT uplink subcarrier spacing
%                           ('3.75kHz','15kHz')
%   Windowing             - Optional. The number of time-domain samples
%                           over which the function applies windowing and
%                           overlapping of OFDM symbols. The default
%                           depends on the NPRACH preamble format. For more
%                           information, see <a href="matlab:
%                           doc('lteNPRACHInfo')">lteNPRACHInfo</a>.
%
%   CHS must be a structure including these fields:
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
%   NInit            - Optional. Initial subcarrier for NPRACH
%                      (0...NumSubcarriers-1) (default 0)
%
%   The structure INFO contains NPRACH information in these fields:
%   SubcarrierSpacing   - Subcarrier spacing in Hz.
%   Nfft                - The number of FFT points used in the OFDM
%                         modulator.
%   SamplingRate        - The sampling rate of the NPRACH modulator. It is
%                         equal to the sampling rate used by
%                         lteSCFDMAModulate. For more information, see
%                         <a href="matlab:doc('lteSCFDMAModulate')"
%                         >lteSCFDMAModulate</a>.
%   Windowing           - The number of time-domain samples over which the
%                         function applies windowing and overlapping of
%                         OFDM symbols.
%   FrequencyLocation   - Frequency location for all the symbol groups in
%                         an NPRACH transmission. (nRA_sc)
%   K                   - Ratio of uplink data to NPRACH subcarrier
%                         spacing. (K)
%   NULSC               - Number of subcarriers for the given uplink
%                         bandwidth. (NUL_sc)
%   PreambleParameters  - Structure containing the random access preamble
%                         parameters for the preamble format
%                         CHS.NPRACHFormat and frame structure type 1,
%                         as per TS 36.211 Table 10.1.6.1-1.
%                         PreambleParameters contains these fields:
%       G               - Number of time-contiguous symbol groups
%       P               - Total number of symbol groups
%       N               - Number of symbols in a symbol group
%       T_CP            - Cyclic prefix length (in units of T_s)
%       T_SEQ           - Length of the symbols in a symbol group (in units
%                         of T_s)
%
%   Example:
%   % Find the frequency location of all the symbol groups in an NPRACH
%   % repetition.
%
%   ue.NNCellID = 0;
%   ue.NBULSubcarrierSpacing = '15kHz';
%   chs.NPRACHFormat = '0';
%   chs.Periodicity = 80;
%   chs.SubcarrierOffset = 0;
%   chs.NumSubcarriers = 12;
%   chs.NRep = 1;
%   nprachInfo = lteNPRACHInfo(ue,chs);
%   disp(nprachInfo.FrequencyLocation)
%
%   See also lteNPRACH.

%   Copyright 2020 The MathWorks, Inc.

function info = lteNPRACHInfo(ue,chs)
    
    % Validate parameters.
    [ue,chs,N] = validateParameters(ue,chs);
    
    % ---------------------------------------------------------------------
    % SubcarrierSpacing
    % ---------------------------------------------------------------------
    
    % 'SubcarrierSpacing' is the NPRACH subcarrier spacing in Hz and is
    % given by TS 36.211 Table 10.1.6.2-1.
    
    if any(strcmpi(chs.NPRACHFormat,{'0','1'}))
        info.SubcarrierSpacing = 3750;
    else % NPRACHFormat 2
        info.SubcarrierSpacing = 1250;
    end
    
    % ---------------------------------------------------------------------
    % SamplingRate
    % ---------------------------------------------------------------------
    
    % 'SamplingRate' is the sampling rate used for the NPRACH waveform
    % created by lteNPRACH for the current configuration, and will be equal
    % to the sampling rate used by lteSCFDMAModulate for normal uplink data
    % modulation for the same value of resource blocks.
    
    scfdmaInfo = lteSCFDMAInfo(ue);
    info.SamplingRate = scfdmaInfo.SamplingRate;
    
    % ---------------------------------------------------------------------
    % Nfft
    % ---------------------------------------------------------------------
    
    % 'Nfft' is the number of FFT points used for the NPRACH waveform
    % created by lteNPRACH for the current configuration.
    
    info.Nfft = info.SamplingRate/info.SubcarrierSpacing;
    
    % ---------------------------------------------------------------------
    % K
    % ---------------------------------------------------------------------
    
    % 'K' is defined in TS 36.211 Section 10.1.6.2 as the ratio between the
    % uplink data subcarrier spacing and the NPRACH subcarrier
    % spacing (INFO.SubcarrierSpacing defined above). The uplink data
    % subcarrier spacing is given by TS 36.211 Table 10.1.2.1-1, according
    % to the number of uplink subcarriers defined from the
    % NBULSubcarrierSpacing field in the input structure UE.
    
    ULSubcarrierSpacing = str2double(strrep(lower(ue.NBULSubcarrierSpacing),'khz',''));
    info.K = ULSubcarrierSpacing*1000 / info.SubcarrierSpacing;
    
    % ---------------------------------------------------------------------
    % NULSC
    % ---------------------------------------------------------------------
    
    % 'NULSC' is defined in TS 36.211 Table 10.1.2.1-1 as the number of
    % subcarriers available for the selected uplink bandwidth.
    
    info.NULSC = 12*15/ULSubcarrierSpacing;
    
    % Check that the number of subcarriers needed does not exceed the
    % total number of subcarriers available.
    if (chs.SubcarrierOffset + chs.NumSubcarriers) > info.K*info.NULSC
        error('lte:error','For preamble format = ''%s'', the sum of SubcarrierOffset (%s) and NumSubcarriers (%s) cannot exceed %s.', ...
            chs.NPRACHFormat,num2str(chs.SubcarrierOffset),num2str(chs.NumSubcarriers),num2str(info.K*info.NULSC))
    end
    
    % ---------------------------------------------------------------------
    % PreambleParameters
    % ---------------------------------------------------------------------
    
    % TS 36.211 Table 10.1.6.1-1 defines these NPRACH parameters for frame
    % structure type 1:
    % 'G'              : Number of time-contiguous symbol groups
    % 'P'              : Total number of symbol groups
    % 'N'              : Number of symbols in a symbol group
    % 'T_CP'           : Cyclic prefix length (in units of T_s)
    % 'T_SEQ'          : Length of the symbols in a symbol group (in units
    %                    of T_s)
    %
    % 'PreambleParameters' is a structure containing the random access
    % preamble parameters for the specified frame structure and preamble
    % format CHS.NPRACHFormat.
    params = getParameters(ue,chs);
    info.PreambleParameters = params;
    
    % Check that the NPRACH transmission length in ms is within the maximum
    % allowed length given by CHS.Periodicity. This includes any 40ms gap
    % that might be required to break down the NPRACH transmission in FDD
    % mode.
    if strcmpi(chs.NPRACHFormat,'2')
        contiguousPreambles = 16;
    else
        contiguousPreambles = 64;
    end
    numGaps = fix((chs.NRep-1)/contiguousPreambles); % Number of 40ms gaps to add every 'contiguousPreambles' preambles
    nprachLength = chs.StartTime+chs.NRep*(params.P*(params.T_CP+params.T_SEQ))/30720+numGaps*40;
    if nprachLength > chs.Periodicity
        error('lte:error',['The length of the NPRACH transmission (%s ms) is larger than the maximum allowed transmission length given by the Periodicity (%s ms).\n'...
            'The length of the NPRACH transmission is affected by NPRACHFormat (''%s''), Periodicity (%s), NRep (%s), and StartTime (%s).'], ...
            num2str(nprachLength),num2str(chs.Periodicity),chs.NPRACHFormat,num2str(chs.Periodicity),num2str(chs.NRep),num2str(chs.StartTime))
    end
    
    % ---------------------------------------------------------------------
    % FrequencyLocation
    % ---------------------------------------------------------------------
    
    % Create a vector containing the frequency location of all the symbol
    % groups in an NPRACH transmission, as described in TS 36.211 Section
    % 10.1.6.1.
    
    if strcmpi(chs.NPRACHFormat,'2')
        NRA_sc = 36;
    else
        NRA_sc = 12;
    end
    
    % Frequency index used by the first symbol group.
    nStart = chs.SubcarrierOffset + floor(chs.NInit/NRA_sc)*NRA_sc;
    
    % Get the frequency index of all the symbol groups within an NPRACH
    % transmission period.
    nTildeRA_SC = getNTildeRA_SC(ue,chs,info,NRA_sc);
    info.FrequencyLocation = nStart + nTildeRA_SC;
    
    % ---------------------------------------------------------------------
    % Windowing
    % ---------------------------------------------------------------------
    
    % 'Windowing' is the number of time-domain samples over which windowing
    % and overlapping of OFDM symbols is applied.
    cpLength = params.T_CP/(params.T_SEQ/params.N)*info.Nfft; % Cyclic prefix length in samples
    maxN = info.Nfft-cpLength;
    if cpLength==info.Nfft
        % For NPRACH preamble formats 1 and 2, the cyclic prefix has the
        % same length as one symbol.
        maxN = info.Nfft;
    end
    if isempty(N) % Get default value
        N = defaultWindowing(chs,cpLength);
    end
    if (N>maxN)
        if cpLength==info.Nfft
            error('lte:error','For preamble format = ''%s'', the parameter field Windowing (%s) must be less than or equal to the cyclic prefix length (%s).',...
                chs.NPRACHFormat,num2str(N),num2str(cpLength));
        else
            error('lte:error','For preamble format = ''0'', the parameter field Windowing (%s) must be less than or equal to %s (the IFFT size (%s) minus the cyclic prefix length (%s)).',...
                num2str(N),num2str(maxN),num2str(info.Nfft),num2str(cpLength));
        end
    end
    info.Windowing = N;
    
    % ---------------------------------------------------------------------
    % Re-arrange the display order of the info fields
    % ---------------------------------------------------------------------
    fields = {'SubcarrierSpacing','Nfft','SamplingRate','Windowing','FrequencyLocation','K','NULSC','PreambleParameters'};
    info = orderfields(info,fields);
end

% -------------------------------------------------------------------------
% Local functions
% -------------------------------------------------------------------------

% Validate parameters.
function [ue,chs,N] = validateParameters(ue,chs)
    
    % UE validation.
    ue = mwltelibrary('validateLTEParameters',ue,'NNCellID','NBULSubcarrierSpacing');
    if isfield(ue,'Windowing')
        ue = mwltelibrary('validateLTEParameters',ue,'Windowing');
        N = floor(ue.Windowing(1));
    else
        % Use default value for windowing.
        N = [];
    end
    
    % CHS validation.
    chs = mwltelibrary('validateLTEParameters',chs,'NPRACHFormat','Periodicity','SubcarrierOffset','NumSubcarriers','NRep','StartTime','NInit');
    fmt2 = strcmpi(chs.NPRACHFormat,'2');
    % For all the numerical fields of CHS, cast to double, floor, and take the first element.
    fields = fieldnames(chs);
    for f = 2:numel(fields)
        chs.(fields{f}) = double(floor(chs.(fields{f})(1)));
    end
    % Periodicity
    validPeriodicity = [40,80,160,320,640,1280,2560];
    if fmt2
        validPeriodicity = [validPeriodicity, 5120];
    end
    if ~any(chs.Periodicity == validPeriodicity)
        error('lte:error','For preamble format = ''%s'', the parameter field Periodicity (%s) must be one of (%s).', chs.NPRACHFormat,num2str(chs.Periodicity),regexprep(num2str(validPeriodicity),'\s+',','))
    end
    % SubcarrierOffset
    if fmt2
        validSubcarrierOffset = [0,6,12,18,24,36,42,48,54,60,72,78,84,90,102,108];
    else
        validSubcarrierOffset = [0,2,12,18,24,34,36];
    end
    if ~any(chs.SubcarrierOffset == validSubcarrierOffset)
        error('lte:error','For preamble format = ''%s'', the parameter field SubcarrierOffset (%s) must be one of (%s).', chs.NPRACHFormat,num2str(chs.SubcarrierOffset),regexprep(num2str(validSubcarrierOffset),'\s+',','))
    end
    % NumSubcarriers
    if fmt2
        validNumSubcarriers = [36,72,108,144];
    else
        validNumSubcarriers = [12,24,36,48];
    end
    if ~any(chs.NumSubcarriers == validNumSubcarriers)
        error('lte:error','For preamble format = ''%s'', the parameter field NumSubcarriers (%s) must be one of (%s).', chs.NPRACHFormat,num2str(chs.NumSubcarriers),regexprep(num2str(validNumSubcarriers),'\s+',','))
    end
    % NRep
    validNRep = [1,2,4,8,16,32,64,128];
    if ~any(chs.NRep == validNRep)
        error('lte:error','The parameter field NRep (%s) must be one of (%s).', num2str(chs.NRep),regexprep(num2str(validNRep),'\s+',','))
    end
    % StartTime
    validStartTime = [8,16,32,64,128,256,512,1024];
    if ~any(chs.StartTime == validStartTime)
        error('lte:error','The parameter field StartTime (%s) must be one of (%s).', num2str(chs.StartTime),regexprep(num2str(validStartTime),'\s+',','))
    end
    % NInit
    if chs.NInit >= chs.NumSubcarriers
        error('lte:error','The parameter field NInit (%s) must be less than NumSubcarriers (%s).', num2str(chs.NInit),num2str(chs.NumSubcarriers))
    end
end

% Get NPRACH parameters for the current preamble format from TS 36.211
% Table 10.1.6.1-1.
function params = getParameters(~,chs)

    % Frame structure type 1: Table 10.1.6.1-1
    paramsTable = getTableFS1;

    params = table2struct(paramsTable(strcmpi(chs.NPRACHFormat,paramsTable.PreambleFormat),2:end));
end

% Get TS 36.211 Table 10.1.6.1-1. Values for "T_CP" and "T_SEQ" are in
% units of T_s.
function tableFS1 = getTableFS1
    
    tableFS1 = {
                '0'  4  4  5   2048  5*8192;
                '1'  4  4  5   8192  5*8192;
                '2'  6  6  3  24576  3*24576
               };
    tableFS1 = cell2table(tableFS1,'VariableNames',{'PreambleFormat','G','P','N','T_CP','T_SEQ'});
    tableFS1.Properties.Description = 'TS 36.211 Table 10.1.6.1-1: NPRACH parameters for frame structure type 1';
end

% Get the frequency location nTildeRA_SC of all the symbol groups within an
% NPRACH transmission period, as discussed in TS 36.211 Section 10.1.6.1.
function nTildeRA_SC = getNTildeRA_SC(ue,chs,info,NRA_sc)
    
    % Get values of random access preamble parameters G and P
    G = info.PreambleParameters.G; % Number of contiguous symbol groups in a preamble
    P = info.PreambleParameters.P; % Total number of symbol groups in a preamble
    
    nTildeRA_SC_0 = mod(chs.NInit,NRA_sc);
    numSymbGroups = P*chs.NRep; % Total number of symbol groups
    f = functionF(ue.NNCellID,NRA_sc,numSymbGroups/2);
    
    nTildeRA_SC = zeros(1,numSymbGroups);
    nTildeRA_SC(1) = nTildeRA_SC_0;
    if G==4 && P==4 % NPRACHFormat {'0','1'} of frame structure type 1
        % Loop for each symbol group. Note that the frequency location for
        % the first symbol group has been already computed as nTildeRA_SC_0
        for ii = 2:numSymbGroups
            iiMod = mod(ii-1,4);
            if iiMod==0
                nTildeRA_SC(ii) = mod(nTildeRA_SC_0 + f((ii-1)/4+1), NRA_sc);
            elseif any(iiMod==[1,3]) && mod(nTildeRA_SC(ii-1),2)==0
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) + 1;
            elseif any(iiMod==[1,3]) && mod(nTildeRA_SC(ii-1),2)==1
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) - 1;
            elseif iiMod==2 && nTildeRA_SC(ii-1)<6
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) + 6;
            else % iiMod==2 && nTildeRA_SC(ii-1)>=6
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) - 6;
            end
        end
    elseif G==6 && P==6 % NPRACHFormat '2' of frame structure type 1
        % Loop for each symbol group. Note that the frequency location for
        % the first symbol group has been already computed as nTildeRA_SC_0
        for ii = 2:numSymbGroups
            iiMod = mod(ii-1,6);
            if iiMod==0
                nTildeRA_SC(ii) = mod(nTildeRA_SC_0 + f((ii-1)/6+1), NRA_sc);
            elseif any(iiMod==[1,5]) && mod(nTildeRA_SC(ii-1),2)==0
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) + 1;
            elseif any(iiMod==[1,5]) && mod(nTildeRA_SC(ii-1),2)==1
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) - 1;
            elseif any(iiMod==[2,4]) && mod(floor(nTildeRA_SC(ii-1)/3),2)==0
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) + 3;
            elseif any(iiMod==[2,4]) && mod(floor(nTildeRA_SC(ii-1)/3),2)==1
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) - 3;
            elseif iiMod==3 && nTildeRA_SC(ii-1)<18
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) + 18;
            else % iiMod==3 && nTildeRA_SC(ii-1)>=18
                nTildeRA_SC(ii) = nTildeRA_SC(ii-1) - 18;
            end
        end
    end
end

% Implementation of the anonymous function "f(t)" defined in TS 36.211 Section
% 10.1.6.1. This is used in the determination of the NPRACH frequency
% location.
% The third input "maxT" represents the maximum value the function can be
% called with for the current configuration. Thus, this function returns
% all the "maxT" possible values for "f(t)".
function f = functionF(cInit,NRA_sc,maxT)
    
    t = 0:maxT;
    ii = (1:9)';
    n = 10*t+ii;
    cMax = ltePRBS(cInit,n(end)+1); % ltePRBS is zero based. Using n+1 takes care of it.
    f = zeros(length(t)+1,1);
    for tInd = t+1
        s = mod(sum(cMax(n(:,tInd)+1).*2.^(n(:,tInd)-n(1,tInd))),NRA_sc-1);
        f(tInd+1) = mod(f(tInd)+s+1,NRA_sc);
    end
    f(1) = [];
end

% The number of samples used for windowing depends on the NPRACH preamble
% format. The default is chosen in accordance with the values in TS 36.101,
% Section F.5.F. For preamble format 2, the window length is considered so
% that the ratio between CP length and window length is the same as that
% of preamble format 1.
function N = defaultWindowing(chs,cpLength)
    
    switch chs.NPRACHFormat
        case '0'
            W = 110;
        case '1'
            W = 494;
        case '2'
            W = 1482;
    end
    N = cpLength - W;
end
